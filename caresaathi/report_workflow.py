"""Report Workflow / Report Agent for CareSaathi AI.
Responsible for:
1. Compiling daily/weekly clinician-ready progress summaries (FR-09).
2. Linking tasks to source record IDs and timestamps.
3. Labeling all symptoms and vitals as 'patient-reported'.
4. Aggregating unresolved questions for clinical consults.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from caresaathi.models import ProgressReport, TaskStatus
from caresaathi.db import (
    get_latest_care_plan, get_tasks_for_checklist, get_symptom_entries,
    get_unresolved_questions, get_safety_events, save_progress_report,
    get_task_audit_trail
)


class ReportWorkflow:
    """Specialist workflow for generating traceable clinician-ready progress reports."""

    @staticmethod
    def generate_progress_report(
        synthetic_patient_id: Optional[str] = None,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """FR-09: Generates a structured progress report for the patient to share with their clinician."""
        plan = get_latest_care_plan(synthetic_patient_id)
        patient_name = plan.patient_name if plan else "Synthetic Patient"
        doctor_name = plan.doctor_name if plan else "Treating Clinician"
        diagnosis = plan.diagnosis_context if plan else "Post-Discharge Recovery"

        now = datetime.now()
        start_date = now - timedelta(days=days_back)
        period_start = start_date.strftime("%Y-%m-%d")
        period_end = now.strftime("%Y-%m-%d")
        report_id = f"rep_{int(now.timestamp() * 1000)}"

        # 1. Tasks Summary & Audit
        tasks = get_tasks_for_checklist(synthetic_patient_id)
        task_counts = {
            "total": len(tasks),
            "completed": len([t for t in tasks if t.task_status == TaskStatus.COMPLETED]),
            "skipped": len([t for t in tasks if t.task_status == TaskStatus.SKIPPED]),
            "delayed": len([t for t in tasks if t.task_status == TaskStatus.DELAYED]),
            "pending": len([t for t in tasks if t.task_status == TaskStatus.PENDING]),
        }
        adherence_rate = (
            round((task_counts["completed"] / task_counts["total"]) * 100, 1)
            if task_counts["total"] > 0 else 0.0
        )

        source_record_ids = [t.task_id for t in tasks]

        # 2. Symptom Entries (Patient-reported)
        symptoms = get_symptom_entries(synthetic_patient_id)
        symptom_list = []
        for s in symptoms:
            source_record_ids.append(s.entry_id)
            symptom_list.append({
                "entry_id": s.entry_id,
                "timestamp": s.reported_at,
                "description": s.description,
                "reading": f"{s.optional_reading} {s.unit_if_provided or ''}".strip() if s.optional_reading is not None else "None",
                "source_label": s.source_label,
                "severity": s.emergency_level.value
            })

        # 3. Unresolved Questions & Clarifications
        unresolved = get_unresolved_questions(synthetic_patient_id)
        question_list = [q["question_text"] for q in unresolved]

        # 4. Safety Alerts Triggered
        safety_events = get_safety_events()
        safety_list = []
        for se in safety_events:
            source_record_ids.append(se.event_id)
            safety_list.append({
                "timestamp": se.triggered_at,
                "scenario": se.scenario_code,
                "action": se.action_taken,
                "level": se.emergency_level.value
            })

        # 5. Build Human-Readable Markdown Report
        md_lines = [
            f"# CareSaathi AI - Clinician Progress Report",
            f"**Reporting Period:** {period_start} to {period_end} | **Generated At:** {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Patient:** {patient_name} (ID: {synthetic_patient_id or 'Demo-Patient-01'}) | **Attending Clinician:** {doctor_name}",
            f"**Clinical Context / Diagnosis:** {diagnosis}",
            "",
            "---",
            "### 1. Care Routine & Medication Adherence Summary",
            f"- **Overall Plan Adherence:** {adherence_rate}%",
            f"- **Total Scheduled Tasks:** {task_counts['total']}",
            f"  - Completed: {task_counts['completed']}",
            f"  - Skipped: {task_counts['skipped']}",
            f"  - Delayed: {task_counts['delayed']}",
            f"  - Pending: {task_counts['pending']}",
            "",
            "#### Active Task Breakdown & Traceable Sources:",
        ]

        if tasks:
            md_lines.append("| Task ID | Scheduled Time | Instruction | Status | Source Snippet |")
            md_lines.append("|---|---|---|---|---|")
            for t in tasks:
                time_str = t.scheduled_time_if_explicit or "As scheduled"
                status_badge = t.task_status.value.upper()
                md_lines.append(f"| {t.task_id} | {time_str} | {t.instruction_text} | **{status_badge}** | *\"{t.source_reference}\"* |")
        else:
            md_lines.append("*No active tasks found for this period.*")

        md_lines.extend([
            "",
            "---",
            "### 2. Patient-Reported Symptoms & Vitals Log",
            "> **Notice for Clinician:** All entries in this section are reported directly by the patient or caregiver at home. CareSaathi does not validate or modify patient observations.",
            ""
        ])

        if symptom_list:
            md_lines.append("| Timestamp | Observation / Symptom | Reported Reading | Source Label | Severity |")
            md_lines.append("|---|---|---|---|---|")
            for s in symptom_list:
                md_lines.append(f"| {s['timestamp'][:16]} | {s['description']} | {s['reading']} | `{s['source_label']}` | {s['severity']} |")
        else:
            md_lines.append("*No symptoms or vitals reported during this period.*")

        md_lines.extend([
            "",
            "---",
            "### 3. Ambiguities & Unresolved Questions for Next Consultation",
            "> The following items were detected as ambiguous in the care plan or raised during home care, and require clinician clarification:"
        ])

        if question_list:
            for q in question_list:
                md_lines.append(f"- ❓ {q}")
        else:
            md_lines.append("- *No open ambiguities or questions pending.*")

        if safety_list:
            md_lines.extend([
                "",
                "---",
                "### 4. Safety & Escalation Events Log",
                "| Timestamp | Trigger Scenario | Level | Action Taken |",
                "|---|---|---|---|"
            ])
            for se in safety_list:
                md_lines.append(f"| {se['timestamp'][:16]} | {se['scenario']} | {se['level']} | {se['action']} |")

        md_lines.extend([
            "",
            "---",
            "### Clinical Disclaimer & Data Integrity Note",
            "CareSaathi AI coordinates administrative tracking based solely on doctor-approved plans. "
            "It does not prescribe medications, adjust dosages, or diagnose clinical conditions. "
            "This report is compiled for review by the treating clinician upon patient authorization."
        ])

        report_text = "\n".join(md_lines)

        report = ProgressReport(
            report_id=report_id,
            synthetic_patient_id=synthetic_patient_id or "Demo-Patient-01",
            period_start=period_start,
            period_end=period_end,
            generated_at=now.isoformat(),
            report_text=report_text,
            source_record_ids=source_record_ids,
            task_summary=task_counts,
            symptom_summary=symptom_list,
            unresolved_questions=question_list,
            safety_alerts=safety_list
        )

        save_progress_report(report)

        return {
            "status": "success",
            "report_id": report_id,
            "period": f"{period_start} to {period_end}",
            "adherence_rate": adherence_rate,
            "task_counts": task_counts,
            "total_symptoms": len(symptom_list),
            "unresolved_questions_count": len(question_list),
            "safety_alerts_count": len(safety_list),
            "report_markdown": report_text,
            "message": "Clinician progress report compiled with full audit trail and source links."
        }
