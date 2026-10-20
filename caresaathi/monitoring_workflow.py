"""Monitoring Workflow / Monitoring Agent for CareSaathi AI.
Responsible for:
1. Recording patient-reported symptoms and readings (FR-07).
2. Applying deterministic safety checks without diagnosing (FR-08).
3. Maintaining chronological symptom history for progress reports.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from caresaathi.models import SymptomEntry, SafetyEmergencyLevel
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.db import save_symptom_entry, get_symptom_entries


class MonitoringWorkflow:
    """Specialist workflow for patient-reported symptom logging and monitoring."""

    @staticmethod
    def log_symptom(
        synthetic_patient_id: str,
        description: str,
        optional_reading: Optional[float] = None,
        unit_if_provided: Optional[str] = None,
        reading_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """FR-07: Stores timestamped symptom entry, clearly labeled 'patient-reported', with safety checks."""
        now_iso = datetime.now().isoformat()
        entry_id = f"sym_{int(datetime.now().timestamp() * 1000)}"

        # Evaluate description against deterministic safety rules
        text_eval = SafetyWorkflow.evaluate_text_safety(description)
        emergency_level = SafetyEmergencyLevel(text_eval["emergency_level"])
        safety_message = text_eval.get("message")

        # If a reading is provided, check vitals thresholds as well
        if optional_reading is not None and reading_type:
            vital_level, vital_msg = SafetyWorkflow.evaluate_vital_reading(reading_type, optional_reading)
            if vital_level == SafetyEmergencyLevel.EMERGENCY or emergency_level == SafetyEmergencyLevel.NORMAL:
                emergency_level = vital_level
                safety_message = vital_msg or safety_message

        entry = SymptomEntry(
            entry_id=entry_id,
            synthetic_patient_id=synthetic_patient_id,
            description=description,
            reported_at=now_iso,
            optional_reading=optional_reading,
            unit_if_provided=unit_if_provided,
            reading_type=reading_type,
            source_label="patient-reported",  # Explicitly labeled
            emergency_level=emergency_level,
            safety_message=safety_message
        )

        save_symptom_entry(entry)

        return {
            "status": "success",
            "entry_id": entry_id,
            "patient_id": synthetic_patient_id,
            "description": description,
            "reported_at": now_iso,
            "reading": f"{optional_reading} {unit_if_provided or ''}".strip() if optional_reading is not None else None,
            "source_label": entry.source_label,
            "emergency_level": emergency_level.value,
            "safety_message": safety_message,
            "requires_emergency_action": emergency_level == SafetyEmergencyLevel.EMERGENCY,
            "message": "Symptom logged as patient-reported information. No diagnosis inferred."
        }

    @staticmethod
    def get_symptom_history(synthetic_patient_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns chronological list of patient-reported symptoms."""
        entries = get_symptom_entries(synthetic_patient_id)
        return [
            {
                "entry_id": e.entry_id,
                "description": e.description,
                "reported_at": e.reported_at,
                "reading": f"{e.optional_reading} {e.unit_if_provided or ''}".strip() if e.optional_reading is not None else None,
                "reading_type": e.reading_type,
                "source_label": e.source_label,
                "emergency_level": e.emergency_level.value,
                "safety_message": e.safety_message
            }
            for e in entries
        ]
