"""SQLite database persistence layer for CareSaathi AI.
Provides clean transactional operations, audit trail storage, and schema management.
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any, Generator
from caresaathi.config import DB_PATH
from caresaathi.models import (
    CarePlan, CareTask, TaskEvent, SymptomEntry, SafetyEvent, ProgressReport,
    PlanStatus, ConfirmationStatus, TaskStatus, TaskCategory, SafetyEmergencyLevel
)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager that guarantees transaction commit and connection closure."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initializes SQLite database with all PRD tables."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Care Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS care_plans (
                plan_id TEXT PRIMARY KEY,
                synthetic_patient_id TEXT NOT NULL,
                patient_name TEXT,
                doctor_name TEXT,
                diagnosis_context TEXT,
                source_text TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT
            )
        """)

        # Care Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS care_tasks (
                task_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                category TEXT NOT NULL,
                instruction_text TEXT NOT NULL,
                medication_name TEXT,
                dosage TEXT,
                frequency TEXT,
                scheduled_time_if_explicit TEXT,
                source_reference TEXT NOT NULL,
                confirmation_status TEXT NOT NULL,
                task_status TEXT NOT NULL,
                is_ambiguous INTEGER NOT NULL DEFAULT 0,
                ambiguity_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES care_plans(plan_id)
            )
        """)

        # Task Events table (Audit Trail)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                event_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                previous_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                optional_note TEXT,
                FOREIGN KEY (task_id) REFERENCES care_tasks(task_id)
            )
        """)

        # Symptom Entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS symptom_entries (
                entry_id TEXT PRIMARY KEY,
                synthetic_patient_id TEXT NOT NULL,
                description TEXT NOT NULL,
                reported_at TEXT NOT NULL,
                optional_reading REAL,
                unit_if_provided TEXT,
                reading_type TEXT,
                source_label TEXT NOT NULL DEFAULT 'patient-reported',
                emergency_level TEXT NOT NULL,
                safety_message TEXT
            )
        """)

        # Safety Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS safety_events (
                event_id TEXT PRIMARY KEY,
                scenario_code TEXT NOT NULL,
                triggered_at TEXT NOT NULL,
                trigger_text TEXT NOT NULL,
                action_taken TEXT NOT NULL,
                emergency_level TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                acknowledged_status INTEGER NOT NULL DEFAULT 0,
                emergency_contact_number TEXT
            )
        """)

        # Progress Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress_reports (
                report_id TEXT PRIMARY KEY,
                synthetic_patient_id TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                report_text TEXT NOT NULL,
                source_record_ids TEXT,
                task_summary_json TEXT,
                symptom_summary_json TEXT,
                unresolved_questions_json TEXT,
                safety_alerts_json TEXT,
                disclaimer TEXT NOT NULL
            )
        """)

        # Unresolved Questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unresolved_questions (
                question_id TEXT PRIMARY KEY,
                synthetic_patient_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                source_context TEXT,
                created_at TEXT NOT NULL,
                resolved_status INTEGER NOT NULL DEFAULT 0
            )
        """)


# Database CRUD Operations

def save_care_plan(plan: CarePlan):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM care_tasks WHERE plan_id = ?", (plan.plan_id,))
        cursor.execute("""
            INSERT OR REPLACE INTO care_plans (
                plan_id, synthetic_patient_id, patient_name, doctor_name,
                diagnosis_context, source_text, status, created_at, confirmed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan.plan_id, plan.synthetic_patient_id, plan.patient_name,
            plan.doctor_name, plan.diagnosis_context, plan.source_text,
            plan.status.value, plan.created_at, plan.confirmed_at
        ))

        for task in plan.tasks:
            save_care_task(task, conn=conn)


def save_care_task(task: CareTask, conn: Optional[sqlite3.Connection] = None):
    def _execute(c):
        cursor = c.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO care_tasks (
                task_id, plan_id, category, instruction_text,
                medication_name, dosage, frequency, scheduled_time_if_explicit,
                source_reference, confirmation_status, task_status,
                is_ambiguous, ambiguity_reason, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.task_id, task.plan_id, task.category.value, task.instruction_text,
            task.medication_name, task.dosage, task.frequency, task.scheduled_time_if_explicit,
            task.source_reference, task.confirmation_status.value, task.task_status.value,
            1 if task.is_ambiguous else 0, task.ambiguity_reason,
            task.created_at, task.updated_at
        ))

    if conn is not None:
        _execute(conn)
    else:
        with get_db() as c:
            _execute(c)


def get_care_plan(plan_id: str) -> Optional[CarePlan]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM care_plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute("SELECT * FROM care_tasks WHERE plan_id = ?", (plan_id,))
        task_rows = cursor.fetchall()
        tasks = [row_to_care_task(r) for r in task_rows]

        return CarePlan(
            plan_id=row["plan_id"],
            synthetic_patient_id=row["synthetic_patient_id"],
            patient_name=row["patient_name"],
            doctor_name=row["doctor_name"],
            diagnosis_context=row["diagnosis_context"],
            source_text=row["source_text"],
            status=PlanStatus(row["status"]),
            tasks=tasks,
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"]
        )


def get_latest_care_plan(patient_id: Optional[str] = None) -> Optional[CarePlan]:
    with get_db() as conn:
        cursor = conn.cursor()
        if patient_id:
            cursor.execute(
                "SELECT plan_id FROM care_plans WHERE synthetic_patient_id = ? ORDER BY created_at DESC LIMIT 1",
                (patient_id,)
            )
        else:
            cursor.execute("SELECT plan_id FROM care_plans ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return None
        plan_id = row["plan_id"]
    return get_care_plan(plan_id)


def get_care_task(task_id: str) -> Optional[CareTask]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM care_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return row_to_care_task(row)


def get_tasks_for_checklist(patient_id: Optional[str] = None) -> List[CareTask]:
    with get_db() as conn:
        cursor = conn.cursor()
        if patient_id:
            query = """
                SELECT ct.* FROM care_tasks ct
                JOIN care_plans cp ON ct.plan_id = cp.plan_id
                WHERE cp.synthetic_patient_id = ? AND ct.confirmation_status = 'confirmed'
                ORDER BY ct.scheduled_time_if_explicit ASC, ct.category ASC
            """
            cursor.execute(query, (patient_id,))
        else:
            query = """
                SELECT ct.* FROM care_tasks ct
                WHERE ct.confirmation_status = 'confirmed'
                ORDER BY ct.scheduled_time_if_explicit ASC, ct.category ASC
            """
            cursor.execute(query)
        rows = cursor.fetchall()
        return [row_to_care_task(r) for r in rows]


def update_task_status_with_event(
    task_id: str,
    new_status: TaskStatus,
    optional_note: Optional[str] = None
) -> Optional[TaskEvent]:
    task = get_care_task(task_id)
    if not task:
        return None

    prev_status = task.task_status
    now_iso = datetime.now().isoformat()
    task.task_status = new_status
    task.updated_at = now_iso

    event_id = f"evt_{int(datetime.now().timestamp() * 1000)}"
    event = TaskEvent(
        event_id=event_id,
        task_id=task_id,
        previous_status=prev_status,
        new_status=new_status,
        timestamp=now_iso,
        optional_note=optional_note
    )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE care_tasks SET task_status = ?, updated_at = ? WHERE task_id = ?
        """, (new_status.value, now_iso, task_id))

        cursor.execute("""
            INSERT INTO task_events (event_id, task_id, previous_status, new_status, timestamp, optional_note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.event_id, event.task_id, event.previous_status.value,
            event.new_status.value, event.timestamp, event.optional_note
        ))

    return event


def get_task_audit_trail(task_id: Optional[str] = None) -> List[TaskEvent]:
    with get_db() as conn:
        cursor = conn.cursor()
        if task_id:
            cursor.execute("SELECT * FROM task_events WHERE task_id = ? ORDER BY timestamp DESC", (task_id,))
        else:
            cursor.execute("SELECT * FROM task_events ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        return [
            TaskEvent(
                event_id=r["event_id"],
                task_id=r["task_id"],
                previous_status=TaskStatus(r["previous_status"]),
                new_status=TaskStatus(r["new_status"]),
                timestamp=r["timestamp"],
                optional_note=r["optional_note"]
            )
            for r in rows
        ]


def save_symptom_entry(entry: SymptomEntry):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO symptom_entries (
                entry_id, synthetic_patient_id, description, reported_at,
                optional_reading, unit_if_provided, reading_type,
                source_label, emergency_level, safety_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_id, entry.synthetic_patient_id, entry.description,
            entry.reported_at, entry.optional_reading, entry.unit_if_provided,
            entry.reading_type, entry.source_label, entry.emergency_level.value,
            entry.safety_message
        ))


def get_symptom_entries(patient_id: Optional[str] = None) -> List[SymptomEntry]:
    with get_db() as conn:
        cursor = conn.cursor()
        if patient_id:
            cursor.execute(
                "SELECT * FROM symptom_entries WHERE synthetic_patient_id = ? ORDER BY reported_at DESC",
                (patient_id,)
            )
        else:
            cursor.execute("SELECT * FROM symptom_entries ORDER BY reported_at DESC")
        rows = cursor.fetchall()
        return [
            SymptomEntry(
                entry_id=r["entry_id"],
                synthetic_patient_id=r["synthetic_patient_id"],
                description=r["description"],
                reported_at=r["reported_at"],
                optional_reading=r["optional_reading"],
                unit_if_provided=r["unit_if_provided"],
                reading_type=r["reading_type"],
                source_label=r["source_label"],
                emergency_level=SafetyEmergencyLevel(r["emergency_level"]),
                safety_message=r["safety_message"]
            )
            for r in rows
        ]


def save_safety_event(event: SafetyEvent):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO safety_events (
                event_id, scenario_code, triggered_at, trigger_text,
                action_taken, emergency_level, rule_version, acknowledged_status,
                emergency_contact_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id, event.scenario_code, event.triggered_at,
            event.trigger_text, event.action_taken, event.emergency_level.value,
            event.rule_version, 1 if event.acknowledged_status else 0,
            event.emergency_contact_number
        ))


def get_safety_events() -> List[SafetyEvent]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM safety_events ORDER BY triggered_at DESC")
        rows = cursor.fetchall()
        return [
            SafetyEvent(
                event_id=r["event_id"],
                scenario_code=r["scenario_code"],
                triggered_at=r["triggered_at"],
                trigger_text=r["trigger_text"],
                action_taken=r["action_taken"],
                emergency_level=SafetyEmergencyLevel(r["emergency_level"]),
                rule_version=r["rule_version"],
                acknowledged_status=bool(r["acknowledged_status"]),
                emergency_contact_number=r["emergency_contact_number"]
            )
            for r in rows
        ]


def add_unresolved_question(
    patient_id: str,
    question_text: str,
    source_context: Optional[str] = None
) -> str:
    qid = f"q_{int(datetime.now().timestamp() * 1000)}"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO unresolved_questions (
                question_id, synthetic_patient_id, question_text,
                source_context, created_at, resolved_status
            ) VALUES (?, ?, ?, ?, ?, 0)
        """, (qid, patient_id, question_text, source_context, datetime.now().isoformat()))
    return qid


def get_unresolved_questions(patient_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        if patient_id:
            cursor.execute(
                "SELECT * FROM unresolved_questions WHERE synthetic_patient_id = ? AND resolved_status = 0 ORDER BY created_at DESC",
                (patient_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM unresolved_questions WHERE resolved_status = 0 ORDER BY created_at DESC"
            )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def save_progress_report(report: ProgressReport):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO progress_reports (
                report_id, synthetic_patient_id, period_start, period_end,
                generated_at, report_text, source_record_ids,
                task_summary_json, symptom_summary_json, unresolved_questions_json,
                safety_alerts_json, disclaimer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.report_id, report.synthetic_patient_id, report.period_start,
            report.period_end, report.generated_at, report.report_text,
            json.dumps(report.source_record_ids),
            json.dumps(report.task_summary),
            json.dumps(report.symptom_summary),
            json.dumps(report.unresolved_questions),
            json.dumps(report.safety_alerts),
            report.disclaimer
        ))


def get_progress_reports(patient_id: Optional[str] = None) -> List[ProgressReport]:
    with get_db() as conn:
        cursor = conn.cursor()
        if patient_id:
            cursor.execute(
                "SELECT * FROM progress_reports WHERE synthetic_patient_id = ? ORDER BY generated_at DESC",
                (patient_id,)
            )
        else:
            cursor.execute("SELECT * FROM progress_reports ORDER BY generated_at DESC")
        rows = cursor.fetchall()
        reports = []
        for r in rows:
            reports.append(ProgressReport(
                report_id=r["report_id"],
                synthetic_patient_id=r["synthetic_patient_id"],
                period_start=r["period_start"],
                period_end=r["period_end"],
                generated_at=r["generated_at"],
                report_text=r["report_text"],
                source_record_ids=json.loads(r["source_record_ids"]) if r["source_record_ids"] else [],
                task_summary=json.loads(r["task_summary_json"]) if r["task_summary_json"] else {},
                symptom_summary=json.loads(r["symptom_summary_json"]) if r["symptom_summary_json"] else [],
                unresolved_questions=json.loads(r["unresolved_questions_json"]) if r["unresolved_questions_json"] else [],
                safety_alerts=json.loads(r["safety_alerts_json"]) if r["safety_alerts_json"] else [],
                disclaimer=r["disclaimer"]
            ))
        return reports


def row_to_care_task(r: sqlite3.Row) -> CareTask:
    return CareTask(
        task_id=r["task_id"],
        plan_id=r["plan_id"],
        category=TaskCategory(r["category"]),
        instruction_text=r["instruction_text"],
        medication_name=r["medication_name"],
        dosage=r["dosage"],
        frequency=r["frequency"],
        scheduled_time_if_explicit=r["scheduled_time_if_explicit"],
        source_reference=r["source_reference"],
        confirmation_status=ConfirmationStatus(r["confirmation_status"]),
        task_status=TaskStatus(r["task_status"]),
        is_ambiguous=bool(r["is_ambiguous"]),
        ambiguity_reason=r["ambiguity_reason"],
        created_at=r["created_at"],
        updated_at=r["updated_at"]
    )
