"""FastAPI Web Server for CareSaathi AI.
Provides REST API endpoints and serves the modern interactive dashboard.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path

from caresaathi.models import TaskStatus, ConfirmationStatus
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.routine_workflow import RoutineWorkflow
from caresaathi.monitoring_workflow import MonitoringWorkflow
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.report_workflow import ReportWorkflow
from caresaathi.orchestrator import CareSaathiOrchestrator
from caresaathi.agent import get_agent_info, execute_agent_tool
from caresaathi.db import (
    init_db, get_latest_care_plan, get_task_audit_trail,
    get_symptom_entries, get_safety_events, get_unresolved_questions
)
from synthetic_data.sample_plans import SAMPLE_PLANS, SAFETY_TEST_CASES


app = FastAPI(
    title="CareSaathi AI API",
    description="Doctor-Guided Home Care Coordination Agent with Traceable Care-to-Action",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = CareSaathiOrchestrator()
STATIC_DIR = Path(__file__).resolve().parent / "static"


# Request / Response Schemas
class CarePlanInput(BaseModel):
    plan_id: Optional[str] = None
    patient_id: str = "Demo-Patient-01"
    patient_name: str = "Ramesh Sharma (Synthetic Demo)"
    doctor_name: str = "Dr. K. S. Mehta, MS MCh"
    diagnosis: str = "Post-CABG Surgery Day 7 Home Recovery"
    source_text: str


class ConfirmPlanInput(BaseModel):
    plan_id: str
    task_ids: Optional[List[str]] = None


class TaskUpdateInput(BaseModel):
    task_id: str
    status: str
    note: Optional[str] = None


class SymptomInput(BaseModel):
    patient_id: str = "Demo-Patient-01"
    description: str
    reading: Optional[float] = None
    unit: Optional[str] = None
    reading_type: Optional[str] = None


class SafetyCheckInput(BaseModel):
    text: str


class ChatInput(BaseModel):
    message: str
    patient_id: str = "Demo-Patient-01"


# API Endpoints
@app.get("/api/agent-info")
def api_get_agent_info():
    """Fetch.ai uAgent identity and status (FR-10)."""
    return get_agent_info()


@app.get("/api/synthetic-plans")
def api_get_synthetic_plans():
    """Pre-packaged synthetic clinical plans for one-click testing (FR-12)."""
    return {
        "plans": SAMPLE_PLANS,
        "safety_cases": SAFETY_TEST_CASES
    }


@app.post("/api/care-plan")
def api_create_care_plan(input_data: CarePlanInput):
    """Ingest care plan and extract structured tasks with source links (FR-01, FR-02, FR-03)."""
    plan_id = input_data.plan_id or f"plan_{int(Path(DB_PATH := '').stat().st_mtime if False else 1000)}"
    result = PlanWorkflow.process_new_care_plan(
        plan_id=input_data.plan_id or f"plan_demo_{int(Path().stat().st_mtime)}",
        synthetic_patient_id=input_data.patient_id,
        patient_name=input_data.patient_name,
        doctor_name=input_data.doctor_name,
        diagnosis_context=input_data.diagnosis,
        source_text=input_data.source_text
    )
    return result


@app.post("/api/care-plan/confirm")
def api_confirm_care_plan(input_data: ConfirmPlanInput):
    """Confirmation gate: activates proposed tasks (FR-04)."""
    result = PlanWorkflow.confirm_care_plan(input_data.plan_id, input_data.task_ids)
    return result


@app.get("/api/checklist")
def api_get_checklist(patient_id: Optional[str] = None):
    """Get active daily checklist in chronological order (FR-05)."""
    return RoutineWorkflow.get_daily_checklist(patient_id)


@app.post("/api/task/update")
def api_update_task(input_data: TaskUpdateInput):
    """Update task status with note and timestamp (FR-05, FR-06)."""
    result = RoutineWorkflow.update_task_status(
        task_id=input_data.task_id,
        new_status=input_data.status,
        optional_note=input_data.note
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.get("/api/audit-trail")
def api_get_audit_trail(task_id: Optional[str] = None):
    """Chronological audit trail of all task state changes (FR-06)."""
    return RoutineWorkflow.get_audit_trail(task_id)


@app.post("/api/symptom")
def api_log_symptom(input_data: SymptomInput):
    """Log patient-reported symptom or vital reading (FR-07, FR-08)."""
    result = MonitoringWorkflow.log_symptom(
        synthetic_patient_id=input_data.patient_id,
        description=input_data.description,
        optional_reading=input_data.reading,
        unit_if_provided=input_data.unit,
        reading_type=input_data.reading_type
    )
    return result


@app.get("/api/symptoms")
def api_get_symptoms(patient_id: Optional[str] = None):
    """Patient-reported symptom history."""
    return MonitoringWorkflow.get_symptom_history(patient_id)


@app.post("/api/safety-check")
def api_safety_check(input_data: SafetyCheckInput):
    """Deterministic safety rule evaluation (FR-08)."""
    return SafetyWorkflow.evaluate_text_safety(input_data.text)


@app.get("/api/safety-events")
def api_get_safety_events():
    """List of all safety events and emergency escalations."""
    events = get_safety_events()
    return [e.model_dump() for e in events]


@app.get("/api/unresolved-questions")
def api_get_unresolved_questions(patient_id: Optional[str] = None):
    """List of open questions/ambiguities for next clinician consult."""
    return get_unresolved_questions(patient_id)


@app.get("/api/report")
def api_get_progress_report(patient_id: Optional[str] = None, days_back: int = 7):
    """Generate clinician progress report (FR-09)."""
    return ReportWorkflow.generate_progress_report(patient_id, days_back)


@app.post("/api/chat")
def api_chat(input_data: ChatInput):
    """Chat message routed through CareSaathi Orchestrator & Safety screening."""
    return orchestrator.process_message(input_data.message, input_data.patient_id)


# Serve Static Files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>CareSaathi AI Dashboard</h1><p>UI loading...</p>")
