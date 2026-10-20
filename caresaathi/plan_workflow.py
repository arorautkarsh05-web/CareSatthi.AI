"""Plan Workflow / Plan Agent for CareSaathi AI.
Responsible for:
1. Ingesting clinician-approved care plans (FR-01).
2. Extracting structured tasks with strict source references (FR-02).
3. Flagging ambiguities without hallucinating or guessing clinical details (FR-03).
4. Enforcing the Confirmation Gate before tasks become active (FR-04).
"""
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from caresaathi.models import (
    CarePlan, CareTask, PlanStatus, ConfirmationStatus, TaskStatus, TaskCategory
)
from caresaathi.db import (
    save_care_plan, get_care_plan, save_care_task, add_unresolved_question
)


# Known time keywords mapping to standard explicit times
TIME_PATTERNS = {
    r"\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b": lambda m: normalize_time_str(m.group(1)),
    r"\b(?:in the\s+)?morning\b": lambda m: "08:00 AM",
    r"\b(?:at\s+)?breakfast\b": lambda m: "08:30 AM",
    r"\b(?:at\s+)?noon\b|\blunch\b": lambda m: "01:00 PM",
    r"\b(?:in the\s+)?evening\b": lambda m: "06:00 PM",
    r"\b(?:at\s+)?dinner\b": lambda m: "08:00 PM",
    r"\b(?:at\s+)?bedtime\b|\bat night\b": lambda m: "10:00 PM",
}

# Ambiguity indicator triggers (words indicating missing clinical parameters or conditional vagueness)
AMBIGUOUS_PATTERNS = [
    (r"\b(?:take\s+)?(?:some\s+)?(?:pain|fever|pressure|sugar|cough|allergy)\s+(?:medicine|pill|tablet|syrup)\b", "Missing specific medication name and dosage."),
    (r"\b(?:as needed|prn)\b(?!\s*for\s+specific\s+dose)", "Missing clear administration threshold or upper daily limit."),
    (r"\b(?:if\s+needed|when\s+you\s+feel)\b", "Conditional trigger is medically ambiguous without objective criteria."),
    (r"\b(?:an\s+antibiotic|a\s+blood\s+thinner|water\s+pill)\b", "Generic drug category specified instead of exact medication name."),
    (r"\b(?:increase\s+dose|adjust\s+dose)\s+(?:as\s+tolerated|accordingly)\b", "Dose adjustment requires explicit clinician titration schedule."),
]


def normalize_time_str(raw: str) -> str:
    raw = raw.strip().upper()
    if ":" not in raw:
        # e.g. 8AM -> 08:00 AM
        match = re.match(r"(\d{1,2})\s*(AM|PM)", raw)
        if match:
            h, ampm = match.groups()
            return f"{int(h):02d}:00 {ampm}"
    else:
        match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", raw)
        if match:
            h, m, ampm = match.groups()
            ampm = ampm or "AM"
            return f"{int(h):02d}:{m} {ampm}"
    return raw


class PlanWorkflow:
    """Specialist workflow for care plan parsing, task extraction, and confirmation."""

    @staticmethod
    def extract_tasks_from_text(plan_id: str, text: str) -> List[CareTask]:
        """Parses doctor-approved care plan text into proposed structured tasks with source references."""
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        tasks: List[CareTask] = []
        task_counter = 1

        for line in lines:
            # Skip pure headers or metadata markers
            clean_line = re.sub(r"^[\*\-\•\d\.\)\s]+", "", line).strip()
            if not clean_line or len(clean_line) < 4:
                continue

            # Skip header and metadata lines like "CARE PLAN:", "MEDICATIONS:", "Patient: ...", "Primary Consultant: ...", etc.
            if re.search(r"^(?:CARE PLAN|CLINICAL INSTRUCTIONS|DIAGNOSIS|DOCTOR|PATIENT|PRESCRIPTION|RX|DISCHARGE SUMMARY|MEDICATIONS|MONITORING\s*&\s*MEASUREMENTS|REHABILITATION\s*&\s*DIET|FOLLOW-UP|DAILY MEDICATIONS|MEASUREMENTS|DIET\s*&\s*LIFESTYLE|ENDOCRINE CARE INSTRUCTIONS)[\s:]*$", clean_line, re.IGNORECASE):
                continue
            if re.match(r"^(?:Patient|Age|Ref|Primary Consultant|Consultant|Attending Clinician):", clean_line, re.IGNORECASE):
                continue

            category, med_name, dosage, freq, scheduled_time = PlanWorkflow._parse_line_attributes(clean_line)
            is_ambiguous, ambiguity_reason = PlanWorkflow._detect_ambiguity(clean_line, category, med_name, dosage)

            task_id = f"{plan_id}_t{task_counter:02d}"
            task = CareTask(
                task_id=task_id,
                plan_id=plan_id,
                category=category,
                instruction_text=clean_line,
                medication_name=med_name,
                dosage=dosage,
                frequency=freq,
                scheduled_time_if_explicit=scheduled_time,
                source_reference=line.strip(),
                confirmation_status=ConfirmationStatus.AMBIGUOUS if is_ambiguous else ConfirmationStatus.PROPOSED,
                task_status=TaskStatus.PENDING,
                is_ambiguous=is_ambiguous,
                ambiguity_reason=ambiguity_reason,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            tasks.append(task)
            task_counter += 1

        return tasks

    @staticmethod
    def _parse_line_attributes(line: str) -> Tuple[TaskCategory, Optional[str], Optional[str], Optional[str], Optional[str]]:
        lower = line.lower()

        # Category determination
        category = TaskCategory.GENERAL
        if any(w in lower for w in ["tablet", "tab", "capsule", "cap", "mg", "mcg", "ml", "injection", "drops", "syrup", "take ", "dose", "aspirin", "metformin", "atorvastatin", "amlodipine", "pantoprazole", "losartan", "ramipril"]):
            category = TaskCategory.MEDICATION
        elif any(w in lower for w in ["blood pressure", "bp", "blood sugar", "glucose", "weight", "weigh", "temperature", "pulse", "spo2", "measure", "check"]):
            category = TaskCategory.MEASUREMENT
        elif any(w in lower for w in ["diet", "salt", "fluid", "water", "meal", "carb", "calories", "sodium", "fat"]):
            category = TaskCategory.DIET
        elif any(w in lower for w in ["walk", "exercise", "physiotherapy", "rehab", "deep breathing", "spirometer"]):
            category = TaskCategory.EXERCISE
        elif any(w in lower for w in ["dressing", "wound", "incision", "bandage", "clean"]):
            category = TaskCategory.WOUND_CARE
        elif any(w in lower for w in ["follow up", "appointment", "clinic", "visit", "review with dr"]):
            category = TaskCategory.FOLLOW_UP

        # Medication and dosage extraction (if category is medication)
        med_name = None
        dosage = None
        if category == TaskCategory.MEDICATION:
            dose_match = re.search(r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|tablets?|capsules?))", line, re.IGNORECASE)
            if dose_match:
                dosage = dose_match.group(1).strip()

            # Attempt to extract medicine name (e.g. "Tab Metformin 500mg" -> "Metformin")
            med_match = re.search(r"(?:Tab(?:let)?|Cap(?:sule)?|Syrup|Inj(?:ection)?\.?)?\s*([A-Za-z\-]+(?:\s+[A-Za-z]+)?)\s+(?:\d+(?:\.\d+)?\s*(?:mg|mcg|ml)|once|twice|daily)", line, re.IGNORECASE)
            if med_match:
                candidate = med_match.group(1).strip()
                if candidate.lower() not in ["take", "give", "continue", "start", "stop"]:
                    med_name = candidate

        # Frequency extraction
        freq = None
        if re.search(r"\b(?:once\s+daily|od|every\s+day|daily)\b", lower):
            freq = "Once daily"
        elif re.search(r"\b(?:twice\s+daily|bid|2\s+times\s+a\s+day)\b", lower):
            freq = "Twice daily"
        elif re.search(r"\b(?:thrice\s+daily|tid|3\s+times\s+a\s+day)\b", lower):
            freq = "Three times daily"
        elif re.search(r"\b(?:four\s+times\s+daily|qid)\b", lower):
            freq = "Four times daily"
        elif "as needed" in lower or "prn" in lower:
            freq = "As needed (PRN)"

        # Scheduled time extraction
        scheduled_time = None
        for pattern, extractor in TIME_PATTERNS.items():
            match = re.search(pattern, lower)
            if match:
                scheduled_time = extractor(match)
                break

        return category, med_name, dosage, freq, scheduled_time

    @staticmethod
    def _detect_ambiguity(line: str, category: TaskCategory, med_name: Optional[str], dosage: Optional[str]) -> Tuple[bool, Optional[str]]:
        """FR-03: Detects ambiguity. Never guesses medication, dose, or schedule."""
        lower = line.lower()

        # Check explicit ambiguity patterns
        for pattern, reason in AMBIGUOUS_PATTERNS:
            if re.search(pattern, lower):
                return True, reason

        # Check if classified as medication but lacks identifiable medication or dose
        if category == TaskCategory.MEDICATION:
            if not dosage and not any(w in lower for w in ["apply", "cream", "ointment", "continue existing"]):
                return True, "Medication instruction lacks clear dosage (e.g., mg/ml)."
            if "pill" in lower and not med_name:
                return True, "Specific pharmaceutical name is unspecified."

        return False, None

    @staticmethod
    def process_new_care_plan(
        plan_id: str,
        synthetic_patient_id: str,
        patient_name: str,
        doctor_name: str,
        diagnosis_context: str,
        source_text: str
    ) -> Dict[str, Any]:
        """Ingests a new care plan and produces proposed tasks with confirmation flags."""
        tasks = PlanWorkflow.extract_tasks_from_text(plan_id, source_text)

        care_plan = CarePlan(
            plan_id=plan_id,
            synthetic_patient_id=synthetic_patient_id,
            patient_name=patient_name,
            doctor_name=doctor_name,
            diagnosis_context=diagnosis_context,
            source_text=source_text,
            status=PlanStatus.DRAFT,
            tasks=tasks,
            created_at=datetime.now().isoformat()
        )

        save_care_plan(care_plan)

        # Record any ambiguous tasks as unresolved questions for clinician review
        ambiguous_tasks = [t for t in tasks if t.is_ambiguous]
        for at in ambiguous_tasks:
            add_unresolved_question(
                patient_id=synthetic_patient_id,
                question_text=f"Clarification needed on care instruction: '{at.instruction_text}'. Issue: {at.ambiguity_reason}",
                source_context=at.source_reference
            )

        return {
            "status": "success",
            "plan_id": plan_id,
            "patient_name": patient_name,
            "total_tasks": len(tasks),
            "proposed_tasks": len([t for t in tasks if not t.is_ambiguous]),
            "ambiguous_tasks": len(ambiguous_tasks),
            "tasks": [t.model_dump() for t in tasks],
            "message": "Care plan extracted successfully. Tasks remain in 'proposed' state until confirmed by patient/caregiver."
        }

    @staticmethod
    def confirm_care_plan(
        plan_id: str,
        confirmed_task_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """FR-04: Confirmation gate. Moves proposed tasks to confirmed state."""
        plan = get_care_plan(plan_id)
        if not plan:
            return {"status": "error", "message": f"Care plan '{plan_id}' not found."}

        now_iso = datetime.now().isoformat()
        plan.status = PlanStatus.CONFIRMED
        plan.confirmed_at = now_iso

        confirmed_count = 0
        for task in plan.tasks:
            if confirmed_task_ids is None or task.task_id in confirmed_task_ids:
                if not task.is_ambiguous:
                    task.confirmation_status = ConfirmationStatus.CONFIRMED
                    task.updated_at = now_iso
                    save_care_task(task)
                    confirmed_count += 1
                else:
                    # Ambiguous tasks cannot be activated without clinician clarification
                    task.confirmation_status = ConfirmationStatus.AMBIGUOUS
                    save_care_task(task)

        save_care_plan(plan)

        return {
            "status": "success",
            "plan_id": plan_id,
            "confirmed_tasks_count": confirmed_count,
            "plan_status": plan.status.value,
            "confirmed_at": now_iso,
            "message": f"Confirmation gate passed: {confirmed_count} tasks confirmed and active in daily checklist."
        }
