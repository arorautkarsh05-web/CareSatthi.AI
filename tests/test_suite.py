"""Comprehensive test suite for CareSaathi AI.
Validates FR-01 through FR-12 against PRD acceptance criteria.
"""
import unittest
import os
import shutil
from pathlib import Path
from datetime import datetime

# Setup isolated test database
os.environ["CARESAATHI_DB_TEST"] = "1"
from caresaathi.config import DB_PATH
from caresaathi.models import TaskStatus, ConfirmationStatus, SafetyEmergencyLevel
from caresaathi.db import (
    init_db, get_care_plan, get_care_task, get_tasks_for_checklist,
    get_task_audit_trail, get_symptom_entries, get_safety_events,
    get_progress_reports, get_unresolved_questions
)
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.routine_workflow import RoutineWorkflow
from caresaathi.monitoring_workflow import MonitoringWorkflow
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.report_workflow import ReportWorkflow
from caresaathi.orchestrator import CareSaathiOrchestrator
from caresaathi.agent import execute_agent_tool, get_agent_info
from synthetic_data.sample_plans import SAMPLE_PLANS, SAFETY_TEST_CASES


class TestCareSaathiEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db_file = Path(DB_PATH)
        if db_file.exists():
            db_file.unlink()
        init_db()

    def test_01_care_plan_extraction_and_traceability(self):
        """FR-01, FR-02: Ingests care plan text, extracts structured tasks with source references."""
        plan_data = SAMPLE_PLANS["cardiac_recovery"]
        result = PlanWorkflow.process_new_care_plan(
            plan_id=plan_data["plan_id"],
            synthetic_patient_id=plan_data["patient_id"],
            patient_name=plan_data["patient_name"],
            doctor_name=plan_data["doctor_name"],
            diagnosis_context=plan_data["diagnosis"],
            source_text=plan_data["text"]
        )

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["total_tasks"], 5)

        # Verify plan stored in DB
        plan = get_care_plan(plan_data["plan_id"])
        self.assertIsNotNone(plan)
        self.assertEqual(plan.patient_name, plan_data["patient_name"])

        # FR-02: 100% of tasks must have source references
        for task in plan.tasks:
            self.assertTrue(len(task.source_reference) > 0, f"Task {task.task_id} missing source reference!")
            # FR-04: Tasks must start in PROPOSED state
            self.assertEqual(task.confirmation_status, ConfirmationStatus.PROPOSED)

    def test_02_ambiguity_handling_no_guessing(self):
        """FR-03: Ambiguous instructions flagged, never guesses medication or dose."""
        ambiguous_plan = SAMPLE_PLANS["ambiguous_test_plan"]
        result = PlanWorkflow.process_new_care_plan(
            plan_id=ambiguous_plan["plan_id"],
            synthetic_patient_id=ambiguous_plan["patient_id"],
            patient_name=ambiguous_plan["patient_name"],
            doctor_name=ambiguous_plan["doctor_name"],
            diagnosis_context=ambiguous_plan["diagnosis"],
            source_text=ambiguous_plan["text"]
        )

        self.assertEqual(result["status"], "success")
        self.assertGreater(result["ambiguous_tasks"], 0)

        plan = get_care_plan(ambiguous_plan["plan_id"])
        ambiguous_tasks = [t for t in plan.tasks if t.is_ambiguous]
        self.assertGreaterEqual(len(ambiguous_tasks), 2)

        # Verify unresolved questions were created for clinician clarification
        unresolved = get_unresolved_questions(ambiguous_plan["patient_id"])
        self.assertGreaterEqual(len(unresolved), 2)

    def test_03_confirmation_gate(self):
        """FR-04: Tasks remain proposed until user confirms them."""
        plan_data = SAMPLE_PLANS["cardiac_recovery"]
        plan_id = plan_data["plan_id"]

        # Before confirmation, checklist should not have active tasks for this plan
        checklist_before = RoutineWorkflow.get_daily_checklist(plan_data["patient_id"])
        self.assertEqual(checklist_before["total_tasks"], 0)

        # User confirms plan
        conf_result = PlanWorkflow.confirm_care_plan(plan_id)
        self.assertEqual(conf_result["status"], "success")
        self.assertGreater(conf_result["confirmed_tasks_count"], 0)

        # After confirmation, tasks are active in daily checklist
        checklist_after = RoutineWorkflow.get_daily_checklist(plan_data["patient_id"])
        self.assertEqual(checklist_after["total_tasks"], conf_result["confirmed_tasks_count"])

    def test_04_daily_checklist_and_audit_trail(self):
        """FR-05, FR-06: Task status updates (completed, skipped, delayed) and audit events."""
        plan_data = SAMPLE_PLANS["cardiac_recovery"]
        checklist = RoutineWorkflow.get_daily_checklist(plan_data["patient_id"])
        self.assertGreater(len(checklist["checklist"]), 2)

        task_1 = checklist["checklist"][0]
        task_2 = checklist["checklist"][1]

        # Mark task 1 as completed with a note
        update_1 = RoutineWorkflow.update_task_status(
            task_id=task_1["task_id"],
            new_status="completed",
            optional_note="Taken on time with glass of water."
        )
        self.assertEqual(update_1["status"], "success")
        self.assertEqual(update_1["new_status"], "completed")

        # Mark task 2 as skipped with a note
        update_2 = RoutineWorkflow.update_task_status(
            task_id=task_2["task_id"],
            new_status="skipped",
            optional_note="Clinician advised to hold dose today."
        )
        self.assertEqual(update_2["status"], "success")
        self.assertEqual(update_2["new_status"], "skipped")

        # FR-06: Verify audit trail
        audit = RoutineWorkflow.get_audit_trail(task_1["task_id"])
        self.assertGreater(len(audit), 0)
        self.assertEqual(audit[0]["new_status"], "completed")
        self.assertEqual(audit[0]["note"], "Taken on time with glass of water.")

    def test_05_symptom_logging_and_patient_reported_label(self):
        """FR-07: Symptom logged with timestamp, reading, and 'patient-reported' badge."""
        res = MonitoringWorkflow.log_symptom(
            synthetic_patient_id="PATIENT_RAMESH_62",
            description="Mild headache after waking up",
            optional_reading=128.0,
            unit_if_provided="mmHg",
            reading_type="blood_pressure"
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["source_label"], "patient-reported")

        entries = MonitoringWorkflow.get_symptom_history("PATIENT_RAMESH_62")
        self.assertGreater(len(entries), 0)
        self.assertEqual(entries[0]["source_label"], "patient-reported")

    def test_06_deterministic_safety_policy(self):
        """FR-08: Predefined test cases for emergency triggers and clinical boundaries."""
        for case in SAFETY_TEST_CASES:
            eval_res = SafetyWorkflow.evaluate_text_safety(case["input"])
            expected = case["expected_level"]

            if expected == "emergency":
                self.assertFalse(eval_res["is_safe"], f"Failed for {case['name']}")
                self.assertEqual(eval_res["emergency_level"], "emergency")
                self.assertEqual(eval_res["scenario_code"], case["expected_code"])
                self.assertIn("112", eval_res["message"])

            elif expected == "clinical_block":
                self.assertFalse(eval_res["is_safe"], f"Failed for {case['name']}")
                self.assertEqual(eval_res["emergency_level"], "clinical_block")
                self.assertEqual(eval_res["scenario_code"], case["expected_code"])
                self.assertIn("SAFETY POLICY BLOCK", eval_res["message"])

            elif expected == "normal":
                self.assertTrue(eval_res["is_safe"], f"Failed for {case['name']}")
                self.assertEqual(eval_res["emergency_level"], "normal")

    def test_07_progress_report_generation(self):
        """FR-09: Generates clinician-ready progress report with complete audit history."""
        report = ReportWorkflow.generate_progress_report("PATIENT_RAMESH_62", days_back=7)
        self.assertEqual(report["status"], "success")
        self.assertIn("CareSaathi AI - Clinician Progress Report", report["report_markdown"])
        self.assertIn("Patient-Reported Symptoms", report["report_markdown"])
        self.assertIn("Clinical Disclaimer", report["report_markdown"])
        self.assertGreater(report["task_counts"]["total"], 0)

    def test_08_uagent_tool_execution(self):
        """FR-10: Real Fetch.ai uAgent execution and state-changing tool calls."""
        # 1. Test get_daily_checklist tool
        chk_res = execute_agent_tool("get_daily_checklist", {}, "PATIENT_RAMESH_62")
        self.assertEqual(chk_res["status"], "success")

        # 2. Test generate_progress_report tool
        rep_res = execute_agent_tool("generate_progress_report", {"days_back": 7}, "PATIENT_RAMESH_62")
        self.assertEqual(rep_res["status"], "success")
        self.assertIn("report_markdown", rep_res)

        # 3. Test agent identity & Bech32 address
        info = get_agent_info()
        self.assertTrue(info["address"].startswith("agent1"))
        self.assertEqual(info["name"], "caresaathi_agent")

    def test_09_failure_transparency(self):
        """FR-11: Clear error message when task or plan does not exist."""
        bad_task = RoutineWorkflow.update_task_status("nonexistent_task_999", "completed")
        self.assertEqual(bad_task["status"], "error")
        self.assertIn("not found", bad_task["message"].lower())

    def test_10_missing_medication_timing(self):
        """Improvement C: Missing medication timing must be flagged as ambiguous without guessing."""
        plan_text = "1. Tab Amlodipine 5mg\n2. Check blood pressure every morning at 08:00 AM."
        result = PlanWorkflow.process_new_care_plan(
            plan_id="plan_timing_test",
            synthetic_patient_id="PATIENT_TIMING_TEST",
            patient_name="Timing Test Patient",
            doctor_name="Dr. Test",
            diagnosis_context="Hypertension",
            source_text=plan_text
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["ambiguous_tasks"], 1)

        # Confirm that the ambiguous task mentions timing in reason
        ambiguous_task = [t for t in result["tasks"] if t["is_ambiguous"]][0]
        self.assertIn("timing", ambiguous_task["ambiguity_reason"].lower())

        # Confirmation gate must block the ambiguous task from activating
        conf = PlanWorkflow.confirm_care_plan("plan_timing_test")
        self.assertEqual(conf["confirmed_tasks_count"], 1)  # Only BP check confirmed

        chk = RoutineWorkflow.get_daily_checklist("PATIENT_TIMING_TEST")
        active_ids = [t["task_id"] for t in chk["checklist"]]
        self.assertNotIn(ambiguous_task["task_id"], active_ids)

    def test_11_unconfirmed_care_plan_blocked(self):
        """Improvement B & C: Unconfirmed tasks must not be activated or updated."""
        plan_text = "1. Tab Metformin 500mg twice daily at 08:00 AM and 08:00 PM."
        result = PlanWorkflow.process_new_care_plan(
            plan_id="plan_unconf_test",
            synthetic_patient_id="PATIENT_UNCONF_TEST",
            patient_name="Unconfirmed Patient",
            doctor_name="Dr. Test",
            diagnosis_context="Diabetes",
            source_text=plan_text
        )
        task_id = result["tasks"][0]["task_id"]

        # Attempt to mark task as completed before confirmation gate passes
        update_res = RoutineWorkflow.update_task_status(task_id, "completed")
        self.assertEqual(update_res["status"], "error")
        self.assertIn("unconfirmed", update_res["message"].lower())

    def test_12_unsupported_dosage_changes(self):
        """Improvement C: Dosage change queries must be blocked deterministically."""
        dosage_queries = [
            "Can I increase my dose of Atorvastatin to 80mg?",
            "Can I double my morning dose?",
            "Can I take 2 tablets instead of 1?",
            "Should I cut my dose in half?",
            "Dose badha du kya?",
            "डोज़ बढ़ा दूं क्या?"
        ]
        for query in dosage_queries:
            eval_res = SafetyWorkflow.evaluate_text_safety(query)
            self.assertFalse(eval_res["is_safe"], f"Failed to block dosage change query: {query}")
            self.assertEqual(eval_res["emergency_level"], "clinical_block")
            self.assertEqual(eval_res["scenario_code"], "BLOCK_CHANGE_DOSAGE")
            self.assertIn("SAFETY POLICY BLOCK", eval_res["message"])

    def test_13_failed_storage_operations_graceful_handling(self):
        """Improvement C & D: Failed storage or missing record handling must be graceful."""
        # Nonexistent plan confirmation
        bad_plan_conf = PlanWorkflow.confirm_care_plan("nonexistent_plan_000")
        self.assertEqual(bad_plan_conf["status"], "error")
        self.assertIn("not found", bad_plan_conf["message"].lower())

        # Invalid task status enum
        invalid_status = RoutineWorkflow.update_task_status("any_task", "invalid_status_xyz")
        self.assertEqual(invalid_status["status"], "error")
        self.assertIn("invalid status", invalid_status["message"].lower())

    def test_14_multilingual_safety_workflow(self):
        """Improvement C & D: Deterministic 112 emergency routing across supported languages."""
        multilingual_emergencies = [
            ("सीने में बहुत तेज दर्द हो रहा है", "hi"),
            ("chhati me severe dard aur pasina aa raha hai", "hinglish"),
            ("છાતીમાં ખૂબ દુખાવો થાય છે", "gu"),
            ("বুকে তীব্র ব্যথা হচ্ছে", "bn")
        ]
        for query, lang in multilingual_emergencies:
            res = SafetyWorkflow.evaluate_text_safety(query, language=lang)
            self.assertFalse(res["is_safe"])
            self.assertEqual(res["emergency_level"], "emergency")
            self.assertEqual(res["emergency_contact"], "112")
            self.assertIn("112", res["message"])


if __name__ == "__main__":
    unittest.main()

