"""Data models and schemas for CareSaathi AI.
Follows PRD Section 7 specifications strictly.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class TaskCategory(str, Enum):
    MEDICATION = "medication"
    MEASUREMENT = "measurement"
    DIET = "diet"
    EXERCISE = "exercise"
    WOUND_CARE = "wound_care"
    FOLLOW_UP = "follow_up"
    GENERAL = "general"


class ConfirmationStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DELAYED = "delayed"


class SafetyEmergencyLevel(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    EMERGENCY = "emergency"
    CLINICAL_BLOCK = "clinical_block"


class CareTask(BaseModel):
    task_id: str
    plan_id: str
    category: TaskCategory = TaskCategory.GENERAL
    instruction_text: str
    medication_name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    scheduled_time_if_explicit: Optional[str] = None
    source_reference: str  # Direct quote / snippet from doctor's plan
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PROPOSED
    task_status: TaskStatus = TaskStatus.PENDING
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    emergency_level: Optional[SafetyEmergencyLevel] = None
    safety_warning: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CarePlan(BaseModel):
    plan_id: str
    synthetic_patient_id: str
    patient_name: str = "Synthetic Patient"
    doctor_name: Optional[str] = "Treating Clinician"
    diagnosis_context: Optional[str] = None
    source_text: str
    status: PlanStatus = PlanStatus.DRAFT
    tasks: List[CareTask] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    confirmed_at: Optional[str] = None


class TaskEvent(BaseModel):
    event_id: str
    task_id: str
    previous_status: TaskStatus
    new_status: TaskStatus
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    optional_note: Optional[str] = None


class SymptomEntry(BaseModel):
    entry_id: str
    synthetic_patient_id: str
    description: str
    reported_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    optional_reading: Optional[float] = None
    unit_if_provided: Optional[str] = None
    reading_type: Optional[str] = None  # e.g., blood_pressure, blood_glucose, temperature, spo2
    source_label: str = "patient-reported"
    emergency_level: SafetyEmergencyLevel = SafetyEmergencyLevel.NORMAL
    safety_message: Optional[str] = None


class SafetyEvent(BaseModel):
    event_id: str
    scenario_code: str
    triggered_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    trigger_text: str
    action_taken: str
    emergency_level: SafetyEmergencyLevel
    rule_version: str = "1.0.0"
    acknowledged_status: bool = False
    emergency_contact_number: Optional[str] = None


class ProgressReport(BaseModel):
    report_id: str
    synthetic_patient_id: str
    period_start: str
    period_end: str
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    report_text: str
    source_record_ids: List[str] = Field(default_factory=list)
    task_summary: Dict[str, int] = Field(default_factory=dict)
    symptom_summary: List[Dict[str, Any]] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    safety_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = (
        "This progress summary reflects patient-recorded entries under an existing "
        "clinician-approved care plan. It does not constitute a clinical evaluation or "
        "alteration of medical treatment."
    )
