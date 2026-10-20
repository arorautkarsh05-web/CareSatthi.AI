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
    CarePlan, CareTask, PlanStatus, ConfirmationStatus, TaskStatus, TaskCategory, SafetyEmergencyLevel
)
from caresaathi.db import (
    save_care_plan, get_care_plan, save_care_task, add_unresolved_question
)
from caresaathi.safety_workflow import SafetyWorkflow, NATIONAL_EMERGENCY_NUMBER


# Known time keywords mapping to standard explicit times (ordered by specificity)
TIME_PATTERNS = [
    (r"\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", lambda m: normalize_time_str(m.group(1))),
    (r"\b(?:at\s+)?breakfast\b|\bbefore breakfast\b", lambda m: "08:30 AM"),
    (r"\b(?:at\s+)?lunch\b|\b(?:at\s+)?noon\b", lambda m: "01:00 PM"),
    (r"\b(?:at\s+)?dinner\b", lambda m: "08:00 PM"),
    (r"\b(?:at\s+)?bedtime\b|\bat night\b", lambda m: "10:00 PM"),
    (r"\b(?:in the\s+)?morning\b", lambda m: "08:00 AM"),
    (r"\b(?:in the\s+)?evening\b", lambda m: "06:00 PM"),
]

# Ambiguity indicator triggers (words indicating missing clinical parameters or conditional vagueness)
AMBIGUOUS_PATTERNS = [
    (r"\b(?:take\s+)?(?:some\s+)?(?:pain|fever|pressure|sugar|cough|allergy)\s+(?:medicine|pill|tablet|syrup)\b", "Missing specific medication name and dosage."),
    (r"\b(?:as needed|prn)\b(?!\s*for\s+specific\s+dose)", "Missing clear administration threshold or upper daily limit."),
    (r"\b(?:if\s+needed|when\s+you\s+feel)\b", "Conditional trigger is medically ambiguous without objective criteria."),
    (r"\b(?:an\s+antibiotic|a\s+blood\s+thinner|water\s+pill)\b", "Generic drug category specified instead of exact medication name."),
    (r"\b(?:increase\s+dose|adjust\s+dose)\s+(?:as\s+tolerated|accordingly)\b", "Dose adjustment requires explicit clinician titration schedule."),
    (r"\b(?:stop\s+taking|discontinue|quit\s+taking|avoid)\b", "Discontinuation or negative instruction requires clinical confirmation before altering active routine."),
]

# Section heading keywords used to identify clinical document sections as context rather than actionable tasks
SECTION_HEADING_KEYWORDS = [
    r"CARE\s+PLAN(?:\s*&\s*DISCHARGE\s+INSTRUCTIONS)?",
    r"CLINICAL\s+INSTRUCTIONS?",
    r"DISCHARGE\s+(?:SUMMARY|INSTRUCTIONS?|ADVICE|PLAN)",
    r"ENDOCRINE\s+CARE\s+INSTRUCTIONS?",
    r"(?:DAILY\s+)?MEDICATIONS?(?:\s+(?:SAFETY|MANAGEMENT|INSTRUCTIONS?|SCHEDULE|GUIDANCE|ADVICE))?",
    r"PRESCRIPTIONS?",
    r"\bRX\b",
    r"(?:VITAL\s+)?MONITORING(?:\s*&\s*MEASUREMENTS)?",
    r"MEASUREMENTS?",
    r"VITALS?",
    r"REHABILITATION(?:\s*&\s*DIET)?",
    r"DIET(?:\s*&\s*LIFESTYLE)?",
    r"LIFESTYLE(?:\s*&\s*DIET)?",
    r"DIET",
    r"LIFESTYLE",
    r"EXERCISE(?:\s*&\s*(?:ACTIVITY|REHABILITATION))?",
    r"ACTIVITY",
    r"WOUND\s+CARE",
    r"FOLLOW[\s-]UP(?:\s*(?:INSTRUCTIONS?|SCHEDULE|PLAN|APPOINTMENTS?))?",
    r"GENERAL\s+INSTRUCTIONS?",
    r"INVESTIGATIONS?",
    r"SPECIAL\s+INSTRUCTIONS?",
    r"ORDERS?",
    r"PLAN\s+OF\s+CARE",
    r"INSTRUCTIONS?",
    r"SAFETY(?:\s*TEST)?\s*(?:INSTRUCTIONS?|CHECK|ALERTS?)?",
    r"SAFETY\s*(?:MONITORING|GUIDANCE|PRECAUTIONS?)",
    r"SYMPTOM(?:\s*(?:REPORT|LOG|MONITORING|UPDATE|HISTORY|CHECK))?",
    r"EMERGENCY\s*(?:ALERTS?|SYMPTOMS?|GUIDANCE|INSTRUCTIONS?)?",
]

HEADING_REGEX = re.compile(
    rf"^(?:SECTION\s*\d+[\s:–-]*|PART\s*[A-Z\d]+[\s:–-]*|CATEGORY\s*:\s*)?(?:{'|'.join(SECTION_HEADING_KEYWORDS)})(?:\s*(?:&|AND|\/)\s*[A-Z\s]+)?[\s:]*$",
    re.IGNORECASE
)

# Metadata prefix regex for administrative and clinical demographics (not actionable care tasks)
METADATA_REGEX = re.compile(
    r"^(?:\*\*)?(?:"
    r"Patient(?:\s*(?:Name|ID))?"
    r"|Age"
    r"|Sex"
    r"|Gender"
    r"|DOB|Date\s*of\s*Birth"
    r"|Ref(?:erence)?(?:\s*(?:No|ID|Number))?"
    r"|MRN|UHID|Record(?:\s*(?:ID|No))?|Encounter"
    r"|Clinician|Doctor(?:\s*Name)?|Physician|Primary\s*Consultant|Consultant|Attending\s*(?:Clinician|Physician|Doctor)|Surgeon"
    r"|Diagnosis(?:\s*Context)?|Provisional\s*Diagnosis|Final\s*Diagnosis|Condition|Indication"
    r"|Date|Admission\s*Date|Discharge\s*Date|Date\s*of\s*Discharge|Visit\s*Date"
    r"|Hospital|Clinic|Department|Ward|Bed(?:\s*No)?|Room(?:\s*No)?"
    r")(?:\*\*)?\s*[:–-]"
    r"|^(?:\*\*)?(?:SYNTHETIC[\s_-]*TEST(?:[\s_-]*\d+)?|TEST\s*CASE(?:\s*\d+)?|Ref(?:erence)?(?:\s*(?:No|ID|Number))?\s+[A-Za-z0-9_-]+)(?:\*\*)?(?:\s*[:–-]?|\s|$)",
    re.IGNORECASE
)


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
            stripped_line = line.strip()
            # Clean leading bullets, numbering, or markdown headers for content evaluation
            clean_line = re.sub(r"^(?:[\*\-\•\#\s]*|\d{1,3}[\.\)\-–]\s*)", "", stripped_line).strip()
            # Clean markdown bold, italic, or header markers around the text
            clean_line = re.sub(r"^[*_#]+\s*", "", clean_line).strip()
            clean_line = re.sub(r"\s*[*_#]+$", "", clean_line).strip()
            if not clean_line or len(clean_line) < 3:
                continue

            # Section headings and administrative metadata should NEVER be extracted as care tasks
            if HEADING_REGEX.match(clean_line) or HEADING_REGEX.match(stripped_line):
                continue
            if METADATA_REGEX.match(clean_line) or METADATA_REGEX.match(stripped_line):
                continue

            category, med_name, dosage, freq, scheduled_time = PlanWorkflow._parse_line_attributes(clean_line)
            is_ambiguous, ambiguity_reason = PlanWorkflow._detect_ambiguity(clean_line, category, med_name, dosage, freq, scheduled_time)

            # Evaluate line against deterministic safety rules (emergency red flags & clinical boundaries)
            safety_eval = SafetyWorkflow.evaluate_text_safety(clean_line)
            emergency_level_val = None
            safety_warning_text = None

            if not safety_eval.get("is_safe", True):
                is_ambiguous = True
                emergency_level_str = safety_eval.get("emergency_level")
                if emergency_level_str == SafetyEmergencyLevel.EMERGENCY.value:
                    emergency_level_val = SafetyEmergencyLevel.EMERGENCY
                    safety_warning_text = safety_eval.get("message")
                    ambiguity_reason = (
                        f"🚨 EMERGENCY RED FLAG: Potential emergency symptom detected ({clean_line}). "
                        f"IMMEDIATE ACTION REQUIRED: Seek emergency medical assistance immediately or call {NATIONAL_EMERGENCY_NUMBER} (India). "
                        f"CareSaathi does not diagnose conditions or claim clinical certainty. Do not wait for confirmation."
                    )
                elif emergency_level_str == SafetyEmergencyLevel.CLINICAL_BLOCK.value:
                    emergency_level_val = SafetyEmergencyLevel.CLINICAL_BLOCK
                    safety_warning_text = safety_eval.get("message")
                    sc_code = safety_eval.get("scenario_code")
                    if sc_code == "BLOCK_STOP_MEDICATION":
                        ambiguity_reason = (
                            f"🛑 CLINICAL SAFETY BLOCK: Instruction requests or suggests unauthorized medication discontinuation ({clean_line}). "
                            f"Requires registered clinician review and clarification before any change can be authorized."
                        )
                    elif sc_code == "BLOCK_CHANGE_DOSAGE":
                        ambiguity_reason = (
                            f"🛑 CLINICAL SAFETY BLOCK: Instruction requests or suggests unauthorized medication modification or dosage change ({clean_line}). "
                            f"Requires registered clinician review and clarification before any change can be authorized."
                        )
                    else:
                        ambiguity_reason = (
                            f"🛑 CLINICAL SAFETY BLOCK: {safety_warning_text}"
                        )

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
                source_reference=stripped_line,
                confirmation_status=ConfirmationStatus.AMBIGUOUS if is_ambiguous else ConfirmationStatus.PROPOSED,
                task_status=TaskStatus.PENDING,
                is_ambiguous=is_ambiguous,
                ambiguity_reason=ambiguity_reason,
                emergency_level=emergency_level_val,
                safety_warning=safety_warning_text,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
            tasks.append(task)
            task_counter += 1

        return tasks

    @staticmethod
    def _parse_line_attributes(line: str) -> Tuple[TaskCategory, Optional[str], Optional[str], Optional[str], Optional[str]]:
        lower = line.lower()

        # Category determination with high precision:
        # Check clinician contact, follow-up, and consultation tasks first so clinician interactions
        # (e.g. "Contact clinician for medication clarification") are not miscategorized as medication tasks.
        is_clinician_follow_up = (
            any(re.search(p, lower) for p in [
                r"\b(?:contact|call|reach\s+out(?:\s+to)?|ask|consult(?:ation)?(?:\s+with)?|speak\s+with)\s+(?:the\s+|your\s+|a\s+|an\s+)?(?:treating\s+|primary\s+|attending\s+)?(?:clinician|doctor|physician|consultant|specialist|provider|care\s+team|dr\.?|hospital|clinic)\b",
                r"\b(?:schedule|book|set\s+up)\s+(?:a\s+|an\s+)?(?:clinician\s+|doctor\s+|physician\s+|medical\s+)?(?:consultation|appointment|visit|review|follow[\s-]up)\b",
                r"\b(?:follow[\s-]up|appointment|clinic(?:\s+visit)?|review\s+with\s+dr)\b",
            ])
            and not re.search(r"\b(?:without|unless)\s+(?:consulting|contacting|calling|asking)\b", lower)
        )
        is_primary_med_admin = bool(
            re.match(r"^\s*(?:take|tab|tablet|cap|capsule|inj|injection|syrup|apply|swallow)\b", lower)
            and (
                re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|units?|tablets?|capsules?|drops?)\b", lower)
                or any(m in lower for m in ["aspirin", "metformin", "atorvastatin", "amlodipine", "pantoprazole", "losartan", "ramipril", "insulin", "paracetamol", "clonazepam", "clopidogrel", "levothyroxine", "metoprolol"])
            )
        )

        category = TaskCategory.GENERAL
        if is_clinician_follow_up and not is_primary_med_admin:
            category = TaskCategory.FOLLOW_UP
        else:
            is_med_line = (
                any(re.search(p, lower) for p in [
                    r"\b(?:tab|tablet|cap|capsule|inj|injection|syrup|drops?|pill|water\s+pill|blood\s+thinner|medicine|medication|dose|dosage|antibiotic)\b",
                    r"\b(?:aspirin|metformin|atorvastatin|amlodipine|pantoprazole|losartan|ramipril|insulin|paracetamol|clonazepam|clopidogrel|levothyroxine|metoprolol)\b"
                ]) or (
                    re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|units?)\b", lower) and not re.search(r"\b(?:sodium|salt|water|fluid)\b", lower)
                )
            )
            if is_med_line:
                category = TaskCategory.MEDICATION
            elif any(re.search(p, lower) for p in [r"\b(?:blood pressure|bp|blood sugar|glucose|weight|weigh|temperature|pulse|spo2|measure|check)\b"]):
                category = TaskCategory.MEASUREMENT
            elif any(re.search(p, lower) for p in [r"\b(?:diet|salt|fluid|water|meal|carb|calories|sodium|fat|fasting)\b"]):
                category = TaskCategory.DIET
            elif any(re.search(p, lower) for p in [r"\b(?:walk|walking|exercise|physiotherapy|rehab|deep breathing|spirometer)\b"]):
                category = TaskCategory.EXERCISE
            elif any(re.search(p, lower) for p in [r"\b(?:dressing|wound|incision|bandage|clean)\b"]):
                category = TaskCategory.WOUND_CARE
            elif any(re.search(p, lower) for p in [r"\b(?:follow up|appointment|clinic|visit|review with dr)\b"]):
                category = TaskCategory.FOLLOW_UP

        # Medication and dosage extraction (if category is medication)
        med_name = None
        dosage = None
        if category == TaskCategory.MEDICATION:
            dose_match = re.search(r"(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|tablets?|capsules?|drops?))", line, re.IGNORECASE)
            if dose_match:
                dosage = dose_match.group(1).strip()

            # Attempt to extract medicine name (e.g. "Tab Metformin 500mg" -> "Metformin")
            med_match = re.search(r"(?:Take\s+)?(?:Tab(?:let)?|Cap(?:sule)?|Syrup|Inj(?:ection)?\.?)?\s*([A-Za-z\-]+(?:\s+[A-Za-z]+)?)\s+(?:\d+(?:\.\d+)?\s*(?:mg|mcg|ml|units?)|once|twice|daily)", line, re.IGNORECASE)
            if med_match:
                candidate = med_match.group(1).strip()
                if candidate.lower() not in ["take", "give", "continue", "start", "stop"]:
                    med_name = candidate

        # Frequency extraction (check multi-dose frequencies first so 'twice daily' is not caught by 'daily')
        freq = None
        if re.search(r"\b(?:four\s+times\s+daily|qid|4\s+times\s+a\s+day)\b", lower):
            freq = "Four times daily"
        elif re.search(r"\b(?:thrice\s+daily|three\s+times\s+daily|tid|3\s+times\s+a\s+day)\b", lower):
            freq = "Three times daily"
        elif re.search(r"\b(?:twice\s+daily|two\s+times\s+daily|bid|2\s+times\s+a\s+day)\b", lower):
            freq = "Twice daily"
        elif re.search(r"\b(?:once\s+daily|one\s+time\s+daily|od|every\s+day|daily)\b", lower):
            freq = "Once daily"
        elif "as needed" in lower or "prn" in lower or "sos" in lower:
            freq = "As needed (PRN)"

        # Scheduled time extraction: capture all explicit clock times first, else fall back to named events
        explicit_times = re.findall(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b", line, re.IGNORECASE)
        scheduled_time = None
        if explicit_times:
            normalized = [normalize_time_str(t) for t in explicit_times]
            seen = set()
            deduped = []
            for t in normalized:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            scheduled_time = ", ".join(deduped)
        else:
            for pattern, extractor in TIME_PATTERNS[1:]:
                match = re.search(pattern, lower)
                if match:
                    scheduled_time = extractor(match)
                    break

        return category, med_name, dosage, freq, scheduled_time

    @staticmethod
    def _is_prohibitive_med_instruction(line: str) -> bool:
        """Detects instructions that explicitly prohibit changing, stopping, or altering medication
        (e.g., 'Do not stop the prescribed medicine without consulting the treating clinician'
         or 'Do not increase the prescribed dose without clinician approval').
        These are protective adherence directives and do not represent missing administration dosage.
        """
        lower = line.lower()
        return bool(re.search(
            r"\b(?:do\s+not|don'?t|never|should\s+not|must\s+not|cannot)\s+"
            r"(?:(?:ever\s+)?(?:stop|discontinue|quit|pause|skip|alter|change|modify|adjust|increase|decrease|double|halve|cut)\b|"
            r"take\s+more\b|take\s+less\b)",
            lower
        ))

    @staticmethod
    def _detect_ambiguity(
        line: str,
        category: TaskCategory,
        med_name: Optional[str],
        dosage: Optional[str],
        freq: Optional[str] = None,
        scheduled_time: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """FR-03: Detects ambiguity. Never guesses medication, dose, or schedule."""
        lower = line.lower()

        # If this is an instruction explicitly prohibiting changing or stopping medication,
        # it is a protective adherence instruction. Distinguish it from genuinely missing dosage
        # or administration parameters so it is not incorrectly flagged as ambiguous.
        if PlanWorkflow._is_prohibitive_med_instruction(line):
            return False, None

        # Check explicit ambiguity patterns
        for pattern, reason in AMBIGUOUS_PATTERNS:
            if re.search(pattern, lower):
                return True, reason

        # Check if classified as medication but lacks identifiable medication, dose, or timing
        if category == TaskCategory.MEDICATION:
            if not dosage and not any(w in lower for w in ["apply", "cream", "ointment", "continue existing"]):
                return True, "Medication instruction lacks clear dosage (e.g., mg/ml). Check clinician instructions."
            if "pill" in lower and not med_name:
                return True, "Specific pharmaceutical name is unspecified. Contact clinician for clarification."
            # Check for completely missing timing/frequency
            if not freq and not scheduled_time and not any(w in lower for w in ["as needed", "prn", "sos"]):
                return True, "Medication instruction lacks administration schedule/timing (e.g. morning, daily, bedtime). Please contact clinician."

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

        emergency_tasks = [t for t in tasks if t.emergency_level == SafetyEmergencyLevel.EMERGENCY]
        clinical_blocks = [t for t in tasks if t.emergency_level == SafetyEmergencyLevel.CLINICAL_BLOCK]
        emergency_detected = len(emergency_tasks) > 0

        emergency_message = None
        if emergency_detected:
            emergency_message = (
                f"🚨 EMERGENCY WARNING: Potential emergency red-flag symptoms detected in care input. "
                f"IMMEDIATE ACTION REQUIRED: Seek emergency medical assistance immediately or call {NATIONAL_EMERGENCY_NUMBER} (India). "
                f"CareSaathi does not diagnose medical conditions or claim clinical certainty. Do not delay emergency care."
            )

        msg = "Care plan extracted successfully. Tasks remain in 'proposed' state until confirmed by patient/caregiver."
        if emergency_detected:
            msg = emergency_message
        elif clinical_blocks:
            msg = f"Care plan processed with {len(clinical_blocks)} safety policy blocks flagged for clinician clarification."

        return {
            "status": "success",
            "plan_id": plan_id,
            "patient_name": patient_name,
            "total_tasks": len(tasks),
            "proposed_tasks": len([t for t in tasks if not t.is_ambiguous]),
            "ambiguous_tasks": len(ambiguous_tasks),
            "emergency_detected": emergency_detected,
            "emergency_message": emergency_message,
            "emergency_contact": NATIONAL_EMERGENCY_NUMBER,
            "clinical_blocks_count": len(clinical_blocks),
            "tasks": [t.model_dump() for t in tasks],
            "message": msg
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
