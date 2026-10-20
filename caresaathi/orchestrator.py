"""CareSaathi Orchestrator.
Central coordination engine for intent routing, workflow dispatch, and safety screening.
Follows PRD Section 6 architecture strictly.
"""
import re
from typing import Dict, Any, Optional, List
from caresaathi.models import TaskStatus
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.routine_workflow import RoutineWorkflow
from caresaathi.monitoring_workflow import MonitoringWorkflow
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.report_workflow import ReportWorkflow
from caresaathi.db import init_db, get_latest_care_plan


class CareSaathiOrchestrator:
    """Orchestrates workflows across Plan, Routine, Monitoring, Safety, and Report agents."""

    def __init__(self):
        init_db()

    def process_message(
        self,
        user_message: str,
        patient_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Routes a natural language message or structured command to the proper specialist workflow."""
        text = user_message.strip()
        lower = text.lower()
        patient_id = patient_id or "Demo-Patient-01"

        # 1. Deterministic Safety Check on all incoming text FIRST (PRD Principle 6)
        safety_eval = SafetyWorkflow.evaluate_text_safety(text)
        if not safety_eval["is_safe"]:
            return {
                "intent": "SAFETY_INTERVENTION",
                "status": "blocked" if safety_eval["emergency_level"] == "clinical_block" else "emergency",
                "emergency_level": safety_eval["emergency_level"],
                "emergency_contact": safety_eval.get("emergency_contact"),
                "message": safety_eval["message"],
                "requires_immediate_action": safety_eval.get("requires_immediate_action", False)
            }

        # 2. Intent Detection
        # Intent: Report Generation
        if any(w in lower for w in ["report", "doctor summary", "clinical summary", "weekly summary", "progress summary"]):
            res = ReportWorkflow.generate_progress_report(patient_id)
            return {
                "intent": "GENERATE_REPORT",
                "status": "success",
                "data": res,
                "message": res["message"]
            }

        # Intent: Daily Checklist
        if any(w in lower for w in ["checklist", "today's tasks", "todays tasks", "schedule", "routine", "what do i take today", "my tasks"]):
            res = RoutineWorkflow.get_daily_checklist(patient_id)
            return {
                "intent": "GET_CHECKLIST",
                "status": "success",
                "data": res,
                "message": res["message"]
            }

        # Intent: Confirm Care Plan
        if any(w in lower for w in ["confirm plan", "confirm tasks", "approve plan", "activate plan", "confirm all"]):
            latest_plan = get_latest_care_plan(patient_id)
            if not latest_plan:
                return {
                    "intent": "CONFIRM_PLAN",
                    "status": "error",
                    "message": "No draft care plan found to confirm. Please submit a care plan first."
                }
            res = PlanWorkflow.confirm_care_plan(latest_plan.plan_id)
            return {
                "intent": "CONFIRM_PLAN",
                "status": "success",
                "data": res,
                "message": res["message"]
            }

        # Intent: Task Status Update (e.g. "Mark task p1_t01 as completed" or "completed aspirin")
        update_match = re.search(r"(?:mark|set)?\s*(?:task\s+)?([a-zA-Z0-9_\-]+)\s+(?:as\s+)?(completed|done|skipped|delayed|pending)", lower)
        if update_match:
            task_id, raw_status = update_match.groups()
            status_map = {"done": "completed", "completed": "completed", "skipped": "skipped", "delayed": "delayed", "pending": "pending"}
            res = RoutineWorkflow.update_task_status(task_id, status_map[raw_status])
            return {
                "intent": "UPDATE_TASK",
                "status": res["status"],
                "data": res,
                "message": res["message"]
            }

        # Intent: Symptom Logging (e.g. "I have a headache" or "BP is 130/85" or "Feeling nauseous")
        if any(w in lower for w in ["symptom", "feeling", "pain", "nausea", "headache", "dizzy", "fatigue", "fever", "cough", "swelling", "vomit", "cramp"]):
            res = MonitoringWorkflow.log_symptom(synthetic_patient_id=patient_id, description=text)
            return {
                "intent": "LOG_SYMPTOM",
                "status": "success",
                "data": res,
                "message": res["message"]
            }

        # Intent: Care Plan Setup / Ingestion (multiline or containing typical prescription phrases)
        if "\n" in text or any(w in lower for w in ["tab", "mg", "twice daily", "care plan", "instructions:", "take 1", "take 2"]):
            plan_id = f"plan_{int(datetime.now().timestamp() * 1000)}"
            res = PlanWorkflow.process_new_care_plan(
                plan_id=plan_id,
                synthetic_patient_id=patient_id,
                patient_name="Synthetic Patient",
                doctor_name="Dr. Mehta, MD (Cardiology)",
                diagnosis_context="Post-Interventional Home Care Plan",
                source_text=text
            )
            return {
                "intent": "SET_PLAN",
                "status": "success",
                "data": res,
                "message": res["message"]
            }

        # Fallback informative response with clear capabilities
        return {
            "intent": "GENERAL_QUERY",
            "status": "info",
            "message": (
                "CareSaathi AI is ready to help coordinate your doctor-approved care plan. You can:\n"
                "1. Paste a care plan to extract tasks with source links.\n"
                "2. Say 'confirm plan' to activate proposed tasks.\n"
                "3. Ask for 'today's checklist' to see your routine.\n"
                "4. Update a task (e.g., 'mark plan_t01 as completed').\n"
                "5. Log a symptom or vital reading (e.g., 'logged BP 120/80').\n"
                "6. Say 'generate report' to compile a clinician progress summary."
            )
        }
