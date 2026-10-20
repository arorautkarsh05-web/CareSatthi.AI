"""Routine Workflow / Routine Agent for CareSaathi AI.
Responsible for:
1. Generating the daily care checklist in chronological order (FR-05).
2. Updating task statuses (completed, skipped, delayed) with optional notes (FR-05).
3. Maintaining an immutable audit trail with timestamps and source references (FR-06).
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from caresaathi.models import TaskStatus, ConfirmationStatus, TaskEvent
from caresaathi.db import (
    get_tasks_for_checklist, update_task_status_with_event,
    get_task_audit_trail, get_care_task
)


class RoutineWorkflow:
    """Specialist workflow for routine tracking and daily checklist management."""

    @staticmethod
    def get_daily_checklist(patient_id: Optional[str] = None) -> Dict[str, Any]:
        """FR-05: Retrieves active confirmed tasks sorted by scheduled time."""
        tasks = get_tasks_for_checklist(patient_id)

        # Categorize tasks by status
        pending = [t for t in tasks if t.task_status == TaskStatus.PENDING]
        completed = [t for t in tasks if t.task_status == TaskStatus.COMPLETED]
        skipped = [t for t in tasks if t.task_status == TaskStatus.SKIPPED]
        delayed = [t for t in tasks if t.task_status == TaskStatus.DELAYED]

        checklist_items = []
        for t in tasks:
            checklist_items.append({
                "task_id": t.task_id,
                "plan_id": t.plan_id,
                "category": t.category.value,
                "instruction_text": t.instruction_text,
                "medication_name": t.medication_name,
                "dosage": t.dosage,
                "frequency": t.frequency,
                "scheduled_time": t.scheduled_time_if_explicit or "Anytime / As scheduled",
                "source_reference": t.source_reference,  # FR-06: Preserve source reference
                "status": t.task_status.value,
                "updated_at": t.updated_at
            })

        return {
            "status": "success",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_tasks": len(tasks),
            "counts": {
                "pending": len(pending),
                "completed": len(completed),
                "skipped": len(skipped),
                "delayed": len(delayed)
            },
            "checklist": checklist_items,
            "message": f"Daily checklist retrieved: {len(completed)}/{len(tasks)} completed."
        }

    @staticmethod
    def update_task_status(
        task_id: str,
        new_status: str,
        optional_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """FR-05 & FR-06: Updates task status and logs an audit trail event with timestamp."""
        try:
            status_enum = TaskStatus(new_status.lower())
        except ValueError:
            return {
                "status": "error",
                "message": f"Invalid status '{new_status}'. Allowed values: pending, completed, skipped, delayed."
            }

        task = get_care_task(task_id)
        if not task:
            return {"status": "error", "message": f"Task '{task_id}' not found."}

        if task.confirmation_status != ConfirmationStatus.CONFIRMED:
            return {
                "status": "error",
                "message": f"Cannot update unconfirmed task '{task_id}'. Current confirmation status: {task.confirmation_status.value}."
            }

        event = update_task_status_with_event(task_id, status_enum, optional_note)
        if not event:
            return {"status": "error", "message": f"Failed to record status change for task '{task_id}'."}

        return {
            "status": "success",
            "task_id": task_id,
            "instruction": task.instruction_text,
            "previous_status": event.previous_status.value,
            "new_status": event.new_status.value,
            "timestamp": event.timestamp,
            "optional_note": event.optional_note,
            "source_reference": task.source_reference,
            "message": f"Task '{task_id}' marked as {event.new_status.value}."
        }

    @staticmethod
    def get_audit_trail(task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """FR-06: Returns chronological audit trail of task state changes."""
        events = get_task_audit_trail(task_id)
        return [
            {
                "event_id": e.event_id,
                "task_id": e.task_id,
                "previous_status": e.previous_status.value,
                "new_status": e.new_status.value,
                "timestamp": e.timestamp,
                "note": e.optional_note
            }
            for e in events
        ]
