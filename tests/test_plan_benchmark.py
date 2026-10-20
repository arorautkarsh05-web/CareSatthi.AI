"""Task 2: Source-to-Task Accuracy Benchmark (30 Synthetic Clinical Instructions).
Tests numbers, units, negation, ambiguity detection, and source traceability.
"""
import unittest
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.models import TaskCategory, ConfirmationStatus, SafetyEmergencyLevel
from caresaathi.db import get_tasks_for_checklist


class TestPlanAccuracyBenchmark(unittest.TestCase):
    """30-case synthetic clinical test suite verifying source-to-task precision."""

    TEST_CASES = [
        # 1. Standard single instruction with time
        ("Tab Atorvastatin 40mg at bedtime", {"cat": TaskCategory.MEDICATION, "ambiguous": False, "dosage": "40mg", "time": "10:00 PM"}),
        # 2. Numbered quantity
        ("15-minute gentle walking in the evening", {"cat": TaskCategory.EXERCISE, "ambiguous": False, "time": "06:00 PM"}),
        # 3. Liquid volume
        ("Drink 1.5 liters of water daily", {"cat": TaskCategory.DIET, "ambiguous": False}),
        # 4. Decimal dosage
        ("Tab Ramipril 2.5mg once daily in morning", {"cat": TaskCategory.MEDICATION, "ambiguous": False, "dosage": "2.5mg", "freq": "Once daily", "time": "08:00 AM"}),
        # 5. Unit with mcg
        ("Tab Levothyroxine 50mcg once daily before breakfast", {"cat": TaskCategory.MEDICATION, "ambiguous": False, "dosage": "50mcg", "freq": "Once daily", "time": "08:30 AM"}),
        # 6. Compound sentence with multiple instructions
        ("Take Tab Metformin 500mg twice daily with meals and check fasting blood sugar every morning", {"cat": TaskCategory.MEDICATION, "ambiguous": False}),
        # 7. Explicit negation
        ("Do NOT take Aspirin or ibuprofen under any circumstances", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 8. Ambiguous medicine name
        ("Take pain medicine if needed", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 9. Missing dosage
        ("Tab Pantoprazole once daily before breakfast", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 10. Missing timing/schedule
        ("Tab Amlodipine 5mg", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 11. Conditional vague trigger
        ("Take tablet when you feel breathless", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 12. Non-medication dietary
        ("Strict low-sodium diet with less than 2g salt per day", {"cat": TaskCategory.DIET, "ambiguous": False}),
        # 13. Wound care
        ("Clean sternal wound daily with betadine and keep dry", {"cat": TaskCategory.WOUND_CARE, "ambiguous": False}),
        # 14. Follow-up appointment
        ("Follow up in cardiology clinic after 14 days", {"cat": TaskCategory.FOLLOW_UP, "ambiguous": False}),
        # 15. Vital check with explicit time
        ("Check blood pressure at 09:00 AM and 07:00 PM daily", {"cat": TaskCategory.MEASUREMENT, "ambiguous": False}),
        # 16. Water pill generic ambiguity
        ("Take water pill once daily", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 17. Dose adjustment ambiguity
        ("Increase dose as tolerated", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 18. Antibiotic generic ambiguity
        ("Take an antibiotic for 5 days", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 19. Blood thinner generic ambiguity
        ("Continue taking a blood thinner daily", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 20. PRN without upper limit
        ("Take paracetamol 650mg as needed", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 21. Specific PRN with condition
        ("Tab Paracetamol 650mg SOS for temperature above 100 F", {"cat": TaskCategory.MEDICATION, "ambiguous": False}),
        # 22. Deep breathing exercise
        ("Incentive spirometer exercises 10 breaths every 2 hours", {"cat": TaskCategory.EXERCISE, "ambiguous": False}),
        # 23. Weight check with specific time
        ("Weigh yourself every morning before breakfast", {"cat": TaskCategory.MEASUREMENT, "ambiguous": False, "time": "08:30 AM"}),
        # 24. Fractional tablet
        ("Take 0.5 tablet of Clonazepam 0.25mg at bedtime", {"cat": TaskCategory.MEDICATION, "ambiguous": False, "time": "10:00 PM"}),
        # 25. Negation with stop
        ("Stop taking Clopidogrel 7 days before surgery", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 26. Injection unit
        ("Inj Insulin Glargine 14 units at 10:00 PM daily", {"cat": TaskCategory.MEDICATION, "ambiguous": False, "dosage": "14 units", "time": "10:00 PM"}),
        # 27. Eye drops
        ("Carboxymethylcellulose eye drops 1 drop in both eyes 4 times daily", {"cat": TaskCategory.MEDICATION, "ambiguous": False, "freq": "Four times daily"}),
        # 28. Ambiguous fever medicine
        ("Take fever pill twice a day", {"cat": TaskCategory.MEDICATION, "ambiguous": True}),
        # 29. Fasting instruction
        ("Overnight fasting of 8-10 hours before lipid profile test", {"cat": TaskCategory.DIET, "ambiguous": False}),
        # 30. Sodium restriction with mg
        ("Restrict sodium intake to 1500mg daily", {"cat": TaskCategory.DIET, "ambiguous": False})
    ]

    def test_all_30_clinical_instructions(self):
        """Executes all 30 benchmark cases and asserts zero extraction or source tracking regressions."""
        failures = []
        for i, (text, expected) in enumerate(self.TEST_CASES, 1):
            tasks = PlanWorkflow.extract_tasks_from_text("benchmark_plan", text)
            self.assertTrue(len(tasks) >= 1, f"Case {i}: No task extracted from '{text}'")
            t = tasks[0]

            # Verbatim source reference preservation
            self.assertEqual(t.source_reference, text, f"Case {i}: Source mismatch")

            # Ambiguity match
            if "ambiguous" in expected:
                if t.is_ambiguous != expected["ambiguous"]:
                    failures.append(f"Case {i} '{text[:30]}': expected ambiguous={expected['ambiguous']}, got {t.is_ambiguous} ({t.ambiguity_reason})")

            # Category match
            if "cat" in expected:
                if t.category != expected["cat"]:
                    failures.append(f"Case {i} '{text[:30]}': expected category={expected['cat'].value}, got {t.category.value}")

            # Dosage match if checked
            if "dosage" in expected:
                if t.dosage != expected["dosage"]:
                    failures.append(f"Case {i} '{text[:30]}': expected dosage={expected['dosage']}, got {t.dosage}")

            # Time match if checked
            if "time" in expected:
                if t.scheduled_time_if_explicit != expected["time"]:
                    failures.append(f"Case {i} '{text[:30]}': expected time={expected['time']}, got {t.scheduled_time_if_explicit}")

        self.assertEqual(len(failures), 0, f"Benchmark had {len(failures)} failures:\n" + "\n".join(failures))


class TestTaskExtractionBugFixes(unittest.TestCase):
    """Regression tests for task extraction bug fixes:
    1. Headings are not extracted as tasks.
    2. Patient and clinician metadata are not extracted as tasks.
    3. Ten numbered actionable instructions produce ten logical tasks (not 15).
    4. The three medication instructions are preserved correctly.
    5. Both Metoprolol schedule times are represented correctly.
    6. Every actionable task has the correct original source reference.
    7. Existing ambiguous-instruction and safety tests still pass.
    """

    SYNTHETIC_TEST_PLAN = """CARE PLAN & DISCHARGE INSTRUCTIONS:
Patient: Rajesh Patel | Age: 58 | Reference: SYNTHETIC-TEST-001
Clinician: Dr. Demo Kumar
Diagnosis: Post-MI Cardiac Care & Hypertension

MEDICATIONS:
1. Tab Aspirin 75mg once daily at 08:00 AM after breakfast.
2. Tab Atorvastatin 40mg once daily at 08:00 PM after dinner.
3. Tab Metoprolol Succinate 25mg twice daily at 08:00 AM and 08:00 PM.

VITAL MONITORING:
4. Check blood pressure and pulse rate every morning at 08:00 AM.
5. Record resting heart rate daily in the evening at 06:00 PM.

DIET:
6. Strict low sodium diet with less than 2g salt daily.

LIFESTYLE:
7. 15-minute gentle flat walking in the evening at 06:00 PM.
8. Deep breathing exercises for 10 minutes every morning at 09:00 AM.
9. Avoid heavy weight lifting or strenuous physical strain.

FOLLOW-UP:
10. Hospital review appointment on 28th October with Dr. Mehta for stitch check."""

    def test_01_headings_not_extracted_as_tasks(self):
        """1. Section headings such as MEDICATIONS:, MEDICATION SAFETY:, SYMPTOM REPORT:,
        SAFETY TEST INSTRUCTIONS:, VITAL MONITORING:, MONITORING:, DIET:, LIFESTYLE:, FOLLOW-UP:
        are never extracted as tasks.
        """
        headings = [
            "MEDICATIONS:",
            "MEDICATION SAFETY:",
            "SYMPTOM REPORT:",
            "SAFETY TEST INSTRUCTIONS:",
            "VITAL MONITORING:",
            "MONITORING:",
            "DIET:",
            "LIFESTYLE:",
            "FOLLOW-UP:",
            "CARE PLAN & DISCHARGE INSTRUCTIONS:",
            "MONITORING & MEASUREMENTS:",
            "REHABILITATION & DIET:",
            "### MEDICATIONS:",
            "## DIET & LIFESTYLE",
            "DAILY MEDICATIONS:",
            "SECTION 1: MEDICATIONS:",
            "MEDICATION SAFETY",
            "MONITORING",
        ]
        for heading in headings:
            tasks = PlanWorkflow.extract_tasks_from_text("test_heading_plan", heading)
            self.assertEqual(
                len(tasks), 0,
                f"Heading '{heading}' should not be extracted as a task, but got {len(tasks)} tasks: {[t.instruction_text for t in tasks]}"
            )

    def test_01b_actionable_instructions_with_heading_keywords_preserved(self):
        """Do not accidentally remove an actionable instruction merely because it contains words like 'medication safety'."""
        plan_text = """MEDICATION SAFETY:
1. Discuss medication safety at the follow-up appointment.
2. Review medication safety guidelines with your clinician.
3. Follow medication safety precautions carefully."""
        tasks = PlanWorkflow.extract_tasks_from_text("test_med_safety_plan", plan_text)
        self.assertEqual(len(tasks), 3, f"Expected 3 actionable tasks, got {len(tasks)}")
        self.assertEqual(tasks[0].instruction_text, "Discuss medication safety at the follow-up appointment.")
        self.assertEqual(tasks[0].source_reference, "1. Discuss medication safety at the follow-up appointment.")
        self.assertEqual(tasks[1].instruction_text, "Review medication safety guidelines with your clinician.")
        self.assertEqual(tasks[1].source_reference, "2. Review medication safety guidelines with your clinician.")
        self.assertEqual(tasks[2].instruction_text, "Follow medication safety precautions carefully.")
        self.assertEqual(tasks[2].source_reference, "3. Follow medication safety precautions carefully.")

    def test_02_patient_and_clinician_metadata_not_extracted(self):
        """2. Patient and clinician metadata like 'Reference: SYNTHETIC-TEST-001' and 'Clinician: Dr. Demo Kumar' are not tasks."""
        metadata_lines = [
            "Reference: SYNTHETIC-TEST-001",
            "Clinician: Dr. Demo Kumar",
            "Patient: Rajesh Patel | Age: 58 | Reference: SYNTHETIC-TEST-001",
            "Primary Consultant: Dr. K. S. Mehta, Cardiothoracic Surgery",
            "Diagnosis: Post-MI Cardiac Care & Hypertension",
            "Age: 58",
            "Date: 2026-10-20",
            "Hospital: Apex Heart Institute",
            "Department: Cardiology",
        ]
        for meta in metadata_lines:
            tasks = PlanWorkflow.extract_tasks_from_text("test_meta_plan", meta)
            self.assertEqual(
                len(tasks), 0,
                f"Metadata line '{meta}' should not be extracted as a task, but got {len(tasks)} tasks: {[t.instruction_text for t in tasks]}"
            )

    def test_03_ten_numbered_instructions_produce_ten_tasks(self):
        """3. Ten numbered actionable instructions produce ten logical tasks (resolves 15 tasks bug)."""
        tasks = PlanWorkflow.extract_tasks_from_text("test_10_plan", self.SYNTHETIC_TEST_PLAN)
        self.assertEqual(
            len(tasks), 10,
            f"Expected exactly 10 tasks from 10 numbered instructions, but got {len(tasks)}: {[t.instruction_text for t in tasks]}"
        )

    def test_04_three_medication_instructions_preserved_correctly(self):
        """4. The three medication instructions are preserved correctly (name, dose, frequency, source wording)."""
        tasks = PlanWorkflow.extract_tasks_from_text("test_med_plan", self.SYNTHETIC_TEST_PLAN)
        med_tasks = [t for t in tasks if t.category == TaskCategory.MEDICATION]
        self.assertEqual(len(med_tasks), 3, f"Expected 3 medication tasks, got {len(med_tasks)}")

        # 1. Aspirin
        t1 = med_tasks[0]
        self.assertEqual(t1.medication_name, "Aspirin")
        self.assertEqual(t1.dosage, "75mg")
        self.assertEqual(t1.frequency, "Once daily")
        self.assertEqual(t1.scheduled_time_if_explicit, "08:00 AM")
        self.assertIn("Tab Aspirin 75mg once daily at 08:00 AM after breakfast", t1.instruction_text)
        self.assertEqual(t1.source_reference, "1. Tab Aspirin 75mg once daily at 08:00 AM after breakfast.")

        # 2. Atorvastatin
        t2 = med_tasks[1]
        self.assertEqual(t2.medication_name, "Atorvastatin")
        self.assertEqual(t2.dosage, "40mg")
        self.assertEqual(t2.frequency, "Once daily")
        self.assertEqual(t2.scheduled_time_if_explicit, "08:00 PM")
        self.assertIn("Tab Atorvastatin 40mg once daily at 08:00 PM after dinner", t2.instruction_text)
        self.assertEqual(t2.source_reference, "2. Tab Atorvastatin 40mg once daily at 08:00 PM after dinner.")

        # 3. Metoprolol Succinate
        t3 = med_tasks[2]
        self.assertEqual(t3.medication_name, "Metoprolol Succinate")
        self.assertEqual(t3.dosage, "25mg")
        self.assertEqual(t3.frequency, "Twice daily")
        self.assertIn("Tab Metoprolol Succinate 25mg twice daily at 08:00 AM and 08:00 PM", t3.instruction_text)
        self.assertEqual(t3.source_reference, "3. Tab Metoprolol Succinate 25mg twice daily at 08:00 AM and 08:00 PM.")

    def test_05_both_metoprolol_schedule_times_represented(self):
        """5. Both Metoprolol schedule times (08:00 AM and 08:00 PM) are represented correctly."""
        tasks = PlanWorkflow.extract_tasks_from_text("test_metro_plan", self.SYNTHETIC_TEST_PLAN)
        metro_task = next(t for t in tasks if t.medication_name == "Metoprolol Succinate")
        self.assertIsNotNone(metro_task.scheduled_time_if_explicit)
        self.assertIn("08:00 AM", metro_task.scheduled_time_if_explicit)
        self.assertIn("08:00 PM", metro_task.scheduled_time_if_explicit)
        self.assertEqual(metro_task.scheduled_time_if_explicit, "08:00 AM, 08:00 PM")

    def test_06_every_actionable_task_has_correct_original_source_reference(self):
        """6. Every actionable task has the correct original source reference."""
        tasks = PlanWorkflow.extract_tasks_from_text("test_trace_plan", self.SYNTHETIC_TEST_PLAN)
        original_lines = [l.strip() for l in self.SYNTHETIC_TEST_PLAN.strip().splitlines() if l.strip()]

        for i, task in enumerate(tasks, 1):
            expected_prefix = f"{i}. "
            self.assertTrue(
                task.source_reference.startswith(expected_prefix),
                f"Task {i} source_reference '{task.source_reference}' does not start with '{expected_prefix}'"
            )
            self.assertIn(
                task.source_reference, original_lines,
                f"Task source_reference '{task.source_reference}' not found in original plan lines"
            )
            # Headings or metadata should never be source_reference
            self.assertFalse(task.source_reference.endswith(":"))
            self.assertFalse("SYNTHETIC-TEST-001" in task.source_reference)
            self.assertFalse("Dr. Demo Kumar" in task.source_reference and not "stitch check" in task.source_reference)

    def test_07_ambiguity_and_safety_checks_remain_unweakened(self):
        """7. Ambiguity detection and safety checks remain strict and unweakened."""
        # Unspecified medication name
        amb_tasks = PlanWorkflow.extract_tasks_from_text("plan_amb", "1. Take pain medicine if needed.")
        self.assertEqual(len(amb_tasks), 1)
        self.assertTrue(amb_tasks[0].is_ambiguous)

        # Missing dosage
        amb_dose = PlanWorkflow.extract_tasks_from_text("plan_amb2", "1. Tab Pantoprazole once daily before breakfast.")
        self.assertEqual(len(amb_dose), 1)
        self.assertTrue(amb_dose[0].is_ambiguous)

        # Negation / safety warning
        neg_tasks = PlanWorkflow.extract_tasks_from_text("plan_neg", "1. Stop taking Clopidogrel 7 days before surgery.")
        self.assertEqual(len(neg_tasks), 1)
        self.assertTrue(neg_tasks[0].is_ambiguous)


class TestSyntheticTestCase3SafetyFixes(unittest.TestCase):
    """Regression test suite for synthetic Test Case 3:
    Issue 1: Emergency Symptom Detection
      1. Severe chest pain alone.
      2. Difficulty breathing alone.
      3. Severe chest pain combined with difficulty breathing.
      4. Negated symptoms ("The patient reports no chest pain today.").
      5. Negated symptoms followed by a separate positive emergency symptom ("The patient reports no chest pain today, but has difficulty breathing.").
      6. Emergency warning visibility in actual UI/API response.
    Issue 2: Unsafe Medication Changes
      1. Stopping a prescribed medication ("Stop taking my prescribed medicine because I feel better.").
      2. Increasing a medication dose ("Increase my medication dose as symptoms persist.").
      3. Doubling a missed dose ("Double the missed dose at bedtime.").
      4. Existing clearly specified medication instructions remain unblocked ("Tab Aspirin 75mg once daily at 08:00 AM after breakfast.").
      5. Ensuring safety flags do not incorrectly trigger for unrelated text.
    Issue 3: Section Headings and Administrative Metadata
      1. 'Reference: SYNTHETIC-TEST-003' is not extracted as a task.
      2. 'SAFETY TEST INSTRUCTIONS:' is not extracted as a task.
      3. 'SYMPTOM REPORT:' is not extracted as a task.
      4. Actual numbered instructions preserved with accurate source references.
    Issue 4: Safety Status Consistency
      1. Flagged instructions are marked AMBIGUOUS and not activatable through confirmation workflow.
      2. Emergency guidance is visible in API response even if task category is GENERAL.
      3. Proposed status alone does not bypass safety screening.
    """

    def test_issue1_1_severe_chest_pain_alone(self):
        """Issue 1.1: Detect severe chest pain alone as an emergency red flag with 112 guidance."""
        text = "The patient reports severe chest pain."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_1", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.EMERGENCY)
        self.assertTrue(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)
        self.assertIn("112", t.ambiguity_reason)
        self.assertIn("EMERGENCY RED FLAG", t.ambiguity_reason)
        self.assertEqual(t.source_reference, text)

    def test_issue1_2_difficulty_breathing_alone(self):
        """Issue 1.2: Detect difficulty breathing alone as an emergency red flag with 112 guidance."""
        text = "The patient reports difficulty breathing."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_2", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.EMERGENCY)
        self.assertTrue(t.is_ambiguous)
        self.assertIn("112", t.ambiguity_reason)
        self.assertEqual(t.source_reference, text)

    def test_issue1_3_severe_chest_pain_combined_with_difficulty_breathing(self):
        """Issue 1.3: Severe chest pain combined with difficulty breathing triggers emergency escalation."""
        text = "The patient reports severe chest pain and difficulty breathing."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_3", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.EMERGENCY)
        self.assertTrue(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)
        self.assertIn("112", t.ambiguity_reason)
        self.assertIn("EMERGENCY RED FLAG", t.ambiguity_reason)
        # Source traceability preserved
        self.assertEqual(t.source_reference, text)
        self.assertEqual(t.instruction_text, text)
        # Non-diagnostic: does not diagnose disease
        self.assertNotIn("diagnosed with myocardial infarction", t.ambiguity_reason.lower())

    def test_issue1_4_negated_symptoms_do_not_trigger_emergency(self):
        """Issue 1.4: Negated symptoms like 'The patient reports no chest pain today' do not trigger false emergency."""
        text = "The patient reports no chest pain today."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_4", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertNotEqual(t.emergency_level, SafetyEmergencyLevel.EMERGENCY)
        self.assertFalse(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)

    def test_issue1_5_negated_symptom_followed_by_positive_emergency_symptom(self):
        """Issue 1.5: 'No chest pain, but has difficulty breathing' triggers emergency on positive symptom."""
        text = "The patient reports no chest pain today, but has difficulty breathing."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_5", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.EMERGENCY)
        self.assertTrue(t.is_ambiguous)
        self.assertIn("112", t.ambiguity_reason)

    def test_issue1_6_emergency_warning_visibility_in_api_response(self):
        """Issue 1.6: Emergency warning is visible in API response even if instruction is classified as GENERAL."""
        res = PlanWorkflow.process_new_care_plan(
            plan_id="tc3_api_emerg_plan",
            synthetic_patient_id="synth_pt_tc3",
            patient_name="Synthetic Demo Patient",
            doctor_name="Dr. Testing",
            diagnosis_context="Cardiac Emergency Evaluation",
            source_text="The patient reports severe chest pain and difficulty breathing."
        )
        self.assertTrue(res["emergency_detected"])
        self.assertIsNotNone(res["emergency_message"])
        self.assertIn("112", res["emergency_message"])
        self.assertEqual(res["emergency_contact"], "112")
        self.assertEqual(res["total_tasks"], 1)
        task_data = res["tasks"][0]
        self.assertEqual(task_data["category"], TaskCategory.GENERAL.value)
        self.assertEqual(task_data["emergency_level"], "emergency")
        self.assertIn("112", task_data["ambiguity_reason"])

    def test_issue2_1_stopping_prescribed_medication_blocked(self):
        """Issue 2.1: 'Stop taking my prescribed medicine because I feel better' is blocked from activation."""
        text = "Stop taking my prescribed medicine because I feel better."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_stop", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertTrue(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)
        self.assertIn("CLINICAL SAFETY BLOCK", t.ambiguity_reason)
        # Verbatim text preserved without invented replacement instructions
        self.assertEqual(t.instruction_text, text)
        self.assertEqual(t.source_reference, text)

    def test_issue2_2_increasing_medication_dose_blocked(self):
        """Issue 2.2: Increasing a medication dose is blocked from activation without clinician authorization."""
        text = "Increase my medication dose as symptoms persist."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_inc", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertTrue(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)

    def test_issue2_3_doubling_missed_dose_blocked(self):
        """Issue 2.3: Doubling a missed dose is blocked from activation."""
        text = "Double the missed dose at bedtime."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_double", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertTrue(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)

    def test_issue2_4_clearly_specified_medication_instructions_unblocked(self):
        """Issue 2.4: Clearly specified clinician instructions remain unblocked and proposed."""
        text = "1. Tab Aspirin 75mg once daily at 08:00 AM after breakfast."
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_plan_valid_med", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertIsNone(t.emergency_level)
        self.assertFalse(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertEqual(t.medication_name, "Aspirin")
        self.assertEqual(t.dosage, "75mg")

    def test_issue2_5_safety_flags_do_not_falsely_trigger_on_unrelated_text(self):
        """Issue 2.5: Unrelated instructions do not falsely trigger safety blocks."""
        unrelated_samples = [
            "Drink 1.5 liters of water daily",
            "15-minute gentle walking in the evening",
            "Clean sternal wound daily with betadine and keep dry",
            "Strict low-sodium diet with less than 2g salt per day",
        ]
        for s in unrelated_samples:
            tasks = PlanWorkflow.extract_tasks_from_text("tc3_unrelated", s)
            self.assertEqual(len(tasks), 1)
            t = tasks[0]
            self.assertIsNone(t.emergency_level, f"False emergency on: {s}")
            self.assertFalse(t.is_ambiguous, f"False ambiguity on: {s}")
            self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)

    def test_issue3_headings_and_metadata_not_extracted(self):
        """Issue 3: Section headings and metadata are not extracted as tasks."""
        synthetic_plan_3 = """SAFETY TEST INSTRUCTIONS:
Reference: SYNTHETIC-TEST-003
SYMPTOM REPORT:
1. Tab Atorvastatin 40mg once daily at bedtime.
2. 15-minute gentle walking in the evening."""
        tasks = PlanWorkflow.extract_tasks_from_text("tc3_clean_plan", synthetic_plan_3)
        self.assertEqual(
            len(tasks), 2,
            f"Expected exactly 2 tasks, but got {len(tasks)}: {[t.instruction_text for t in tasks]}"
        )
        task_texts = [t.instruction_text for t in tasks]
        self.assertNotIn("Reference: SYNTHETIC-TEST-003", task_texts)
        self.assertNotIn("SAFETY TEST INSTRUCTIONS:", task_texts)
        self.assertNotIn("SYMPTOM REPORT:", task_texts)

        # Confirm source references are clean and accurate
        self.assertEqual(tasks[0].source_reference, "1. Tab Atorvastatin 40mg once daily at bedtime.")
        self.assertEqual(tasks[1].source_reference, "2. 15-minute gentle walking in the evening.")

    def test_issue4_safety_status_consistency_and_confirmation_gate(self):
        """Issue 4: Flagged tasks are blocked from activation; emergency guidance persists."""
        mixed_plan_text = """CARE PLAN:
1. Tab Aspirin 75mg once daily at 08:00 AM after breakfast.
2. Stop taking my prescribed medicine because I feel better.
3. The patient reports severe chest pain and difficulty breathing."""
        plan_id = "tc3_consistency_plan"
        res = PlanWorkflow.process_new_care_plan(
            plan_id=plan_id,
            synthetic_patient_id="pt_consistency_01",
            patient_name="Synthetic Test Patient",
            doctor_name="Dr. Safety Reviewer",
            diagnosis_context="Test Case 3 Consistency Verification",
            source_text=mixed_plan_text
        )
        self.assertEqual(res["total_tasks"], 3)
        self.assertEqual(res["proposed_tasks"], 1)
        self.assertEqual(res["ambiguous_tasks"], 2)
        self.assertTrue(res["emergency_detected"])
        self.assertEqual(res["clinical_blocks_count"], 1)

        # Attempt confirmation across all tasks
        conf_res = PlanWorkflow.confirm_care_plan(plan_id)
        # Exactly 1 safe task should be confirmed
        self.assertEqual(conf_res["confirmed_tasks_count"], 1)

        # Query checklist from database - only the safe confirmed task must be present
        checklist_tasks = get_tasks_for_checklist("pt_consistency_01")
        self.assertEqual(len(checklist_tasks), 1)
        self.assertEqual(checklist_tasks[0].medication_name, "Aspirin")

        # Verify blocked tasks remain AMBIGUOUS in the plan
        stored_plan = PlanWorkflow.confirm_care_plan(plan_id)
        from caresaathi.db import get_care_plan
        db_plan = get_care_plan(plan_id)
        self.assertIsNotNone(db_plan)
        t_aspirin = next(t for t in db_plan.tasks if "Aspirin" in t.instruction_text)
        t_stop = next(t for t in db_plan.tasks if "Stop taking" in t.instruction_text)
        t_emerg = next(t for t in db_plan.tasks if "severe chest pain" in t.instruction_text)

        self.assertEqual(t_aspirin.confirmation_status, ConfirmationStatus.CONFIRMED)
        self.assertEqual(t_stop.confirmation_status, ConfirmationStatus.AMBIGUOUS)
        self.assertEqual(t_emerg.confirmation_status, ConfirmationStatus.AMBIGUOUS)


class TestMedicationSafetyFalsePositiveFixes(unittest.TestCase):
    """Regression tests for distinguishing routine medication-taking instructions
    from unsafe modification or discontinuation requests (Test Cases A through F).
    """

    def test_a_take_prescribed_tablet_every_morning(self):
        """A. 'Take the prescribed tablet every morning.'
        Must NOT be classified as a request to stop or modify medication.
        Missing dosage details trigger routine clinical clarification without false clinical block.
        """
        text = "Take the prescribed tablet every morning."
        tasks = PlanWorkflow.extract_tasks_from_text("test_routine_med", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.category, TaskCategory.MEDICATION)
        self.assertIsNone(t.emergency_level)
        self.assertTrue(t.is_ambiguous)
        self.assertIn("lacks clear dosage", t.ambiguity_reason.lower())
        self.assertNotIn("CLINICAL SAFETY BLOCK", t.ambiguity_reason)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)
        self.assertEqual(t.source_reference, text)

    def test_b_stop_taking_prescribed_medicine(self):
        """B. 'Stop taking my prescribed medicine because I feel better.'
        Expected: Medication discontinuation safety flag.
        """
        text = "Stop taking my prescribed medicine because I feel better."
        tasks = PlanWorkflow.extract_tasks_from_text("test_stop_med", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertTrue(t.is_ambiguous)
        self.assertIn("CLINICAL SAFETY BLOCK", t.ambiguity_reason)
        self.assertIn("discontinuation", t.ambiguity_reason.lower())
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)

    def test_c_increase_blood_pressure_medicine_dose(self):
        """C. 'Increase my blood pressure medicine dose because my reading is high.'
        Expected: Medication modification safety flag.
        """
        text = "Increase my blood pressure medicine dose because my reading is high."
        tasks = PlanWorkflow.extract_tasks_from_text("test_inc_med", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertTrue(t.is_ambiguous)
        self.assertIn("CLINICAL SAFETY BLOCK", t.ambiguity_reason)
        self.assertIn("dosage change", t.ambiguity_reason.lower())
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)

    def test_d_double_medication_dose_if_missed(self):
        """D. 'Double my medication dose if I miss the previous dose.'
        Expected: Unsafe dose-change instruction flagged.
        """
        text = "Double my medication dose if I miss the previous dose."
        tasks = PlanWorkflow.extract_tasks_from_text("test_double_med", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertTrue(t.is_ambiguous)
        self.assertIn("CLINICAL SAFETY BLOCK", t.ambiguity_reason)
        self.assertIn("dosage change", t.ambiguity_reason.lower())
        self.assertEqual(t.confirmation_status, ConfirmationStatus.AMBIGUOUS)

    def test_e_take_aspirin_75mg_once_daily(self):
        """E. 'Take Aspirin 75 mg once daily at 08:00 AM.'
        Expected: Normal medication instruction, proposed and ready for confirmation.
        """
        text = "Take Aspirin 75 mg once daily at 08:00 AM."
        tasks = PlanWorkflow.extract_tasks_from_text("test_valid_asp", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.category, TaskCategory.MEDICATION)
        self.assertIsNone(t.emergency_level)
        self.assertFalse(t.is_ambiguous)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertEqual(t.medication_name, "Aspirin")

    def test_f_do_not_stop_prescribed_medicine(self):
        """F. 'Do not stop the prescribed medicine without consulting the treating clinician.'
        Expected:
        - Preserve original instruction's meaning and negation.
        - Do not interpret as a request to discontinue medication.
        - Do not generate false discontinuation or dosage-change warning.
        - Do not invent medication name, dosage, or schedule (dosage is None).
        - Distinguish missing medication information from instruction prohibiting changing medication.
        - Status is proposed (ready for confirmation), not ambiguous.
        """
        text = "Do not stop the prescribed medicine without consulting the treating clinician."
        tasks = PlanWorkflow.extract_tasks_from_text("test_neg_stop", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.category, TaskCategory.MEDICATION)
        self.assertIsNone(t.emergency_level)
        self.assertFalse(t.is_ambiguous)
        self.assertIsNone(t.ambiguity_reason)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t.dosage)
        self.assertIsNone(t.medication_name)
        self.assertIsNone(t.scheduled_time_if_explicit)
        self.assertEqual(t.instruction_text, text)
        self.assertEqual(t.source_reference, text)

    def test_g_contact_treating_clinician_for_medication_clarification(self):
        """G. 'Contact the treating clinician for medication clarification.'
        Expected: Categorized as follow_up, no medication dosage validation, proposed status.
        """
        text = "Contact the treating clinician for medication clarification."
        tasks = PlanWorkflow.extract_tasks_from_text("test_clinician_contact", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.category, TaskCategory.FOLLOW_UP)
        self.assertEqual(t.instruction_text, text)
        self.assertEqual(t.source_reference, text)
        self.assertIsNone(t.dosage)
        self.assertFalse(t.is_ambiguous)
        self.assertIsNone(t.ambiguity_reason)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t.emergency_level)

    def test_h_schedule_clinician_consultation(self):
        """H. 'Schedule a clinician consultation.'
        Expected: Categorized as follow_up, proposed status.
        """
        text = "Schedule a clinician consultation."
        tasks = PlanWorkflow.extract_tasks_from_text("test_schedule_consult", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.category, TaskCategory.FOLLOW_UP)
        self.assertEqual(t.instruction_text, text)
        self.assertEqual(t.source_reference, text)
        self.assertIsNone(t.dosage)
        self.assertFalse(t.is_ambiguous)
        self.assertIsNone(t.ambiguity_reason)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t.emergency_level)

    def test_i_ask_clinician_about_missing_medication_dose(self):
        """I. 'Ask the clinician about a missing medication dose.'
        Expected: Categorized as follow_up, no medication dosage validation, proposed status.
        """
        text = "Ask the clinician about a missing medication dose."
        tasks = PlanWorkflow.extract_tasks_from_text("test_ask_clinician_dose", text)
        self.assertEqual(len(tasks), 1)
        t = tasks[0]
        self.assertEqual(t.category, TaskCategory.FOLLOW_UP)
        self.assertEqual(t.instruction_text, text)
        self.assertEqual(t.source_reference, text)
        self.assertIsNone(t.dosage)
        self.assertFalse(t.is_ambiguous)
        self.assertIsNone(t.ambiguity_reason)
        self.assertEqual(t.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t.emergency_level)

    def test_j_follow_up_instructions_with_source_traceability_in_full_plan(self):
        """J. Numbered clinician follow-up instructions preserve exact numbering and source references
        while genuine medication instructions continue undergoing medication safety checks.
        """
        plan_text = """CARE PLAN:
1. Contact the treating clinician for medication clarification.
2. Schedule a clinician consultation.
3. Ask the clinician about a missing medication dose.
4. Tab Metformin 500mg twice daily with meals.
5. Take the prescribed tablet every morning."""
        tasks = PlanWorkflow.extract_tasks_from_text("test_combined_plan", plan_text)
        self.assertEqual(len(tasks), 5)

        # 1. Clinician contact
        self.assertEqual(tasks[0].category, TaskCategory.FOLLOW_UP)
        self.assertEqual(tasks[0].instruction_text, "Contact the treating clinician for medication clarification.")
        self.assertEqual(tasks[0].source_reference, "1. Contact the treating clinician for medication clarification.")
        self.assertFalse(tasks[0].is_ambiguous)
        self.assertEqual(tasks[0].confirmation_status, ConfirmationStatus.PROPOSED)

        # 2. Schedule consultation
        self.assertEqual(tasks[1].category, TaskCategory.FOLLOW_UP)
        self.assertEqual(tasks[1].instruction_text, "Schedule a clinician consultation.")
        self.assertEqual(tasks[1].source_reference, "2. Schedule a clinician consultation.")
        self.assertFalse(tasks[1].is_ambiguous)
        self.assertEqual(tasks[1].confirmation_status, ConfirmationStatus.PROPOSED)

        # 3. Ask clinician about missing dose
        self.assertEqual(tasks[2].category, TaskCategory.FOLLOW_UP)
        self.assertEqual(tasks[2].instruction_text, "Ask the clinician about a missing medication dose.")
        self.assertEqual(tasks[2].source_reference, "3. Ask the clinician about a missing medication dose.")
        self.assertFalse(tasks[2].is_ambiguous)
        self.assertEqual(tasks[2].confirmation_status, ConfirmationStatus.PROPOSED)

        # 4. Genuine valid medication
        self.assertEqual(tasks[3].category, TaskCategory.MEDICATION)
        self.assertEqual(tasks[3].medication_name, "Metformin")
        self.assertEqual(tasks[3].dosage, "500mg")
        self.assertFalse(tasks[3].is_ambiguous)
        self.assertEqual(tasks[3].confirmation_status, ConfirmationStatus.PROPOSED)

        # 5. Genuine medication with missing dose (ambiguity preserved)
        self.assertEqual(tasks[4].category, TaskCategory.MEDICATION)
        self.assertTrue(tasks[4].is_ambiguous)
        self.assertEqual(tasks[4].confirmation_status, ConfirmationStatus.AMBIGUOUS)
        self.assertIn("lacks clear dosage", tasks[4].ambiguity_reason.lower())

    def test_k_prohibitive_and_unauthorized_medication_instructions(self):
        """K. Regression test for the five key medication & adherence instructions:
        1. 'Do not stop the prescribed medicine without consulting the treating clinician.'
        2. 'Stop taking the prescribed medicine because I feel better.'
        3. 'Do not increase the prescribed dose without clinician approval.'
        4. 'Increase my blood pressure medicine dose because my reading is high.'
        5. 'If a dose is missed, contact the treating clinician for guidance.'
        """
        # 1. Do not stop... (prohibitive adherence directive)
        t1_tasks = PlanWorkflow.extract_tasks_from_text("k1", "Do not stop the prescribed medicine without consulting the treating clinician.")
        self.assertEqual(len(t1_tasks), 1)
        t1 = t1_tasks[0]
        self.assertEqual(t1.category, TaskCategory.MEDICATION)
        self.assertFalse(t1.is_ambiguous)
        self.assertIsNone(t1.ambiguity_reason)
        self.assertEqual(t1.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t1.emergency_level)
        self.assertIsNone(t1.dosage)

        # 2. Stop taking... (unauthorized discontinuation request)
        t2_tasks = PlanWorkflow.extract_tasks_from_text("k2", "Stop taking the prescribed medicine because I feel better.")
        self.assertEqual(len(t2_tasks), 1)
        t2 = t2_tasks[0]
        self.assertTrue(t2.is_ambiguous)
        self.assertEqual(t2.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertIn("CLINICAL SAFETY BLOCK", t2.ambiguity_reason)
        self.assertIn("discontinuation", t2.ambiguity_reason.lower())
        self.assertEqual(t2.confirmation_status, ConfirmationStatus.AMBIGUOUS)

        # 3. Do not increase... (prohibitive dose directive)
        t3_tasks = PlanWorkflow.extract_tasks_from_text("k3", "Do not increase the prescribed dose without clinician approval.")
        self.assertEqual(len(t3_tasks), 1)
        t3 = t3_tasks[0]
        self.assertEqual(t3.category, TaskCategory.MEDICATION)
        self.assertFalse(t3.is_ambiguous)
        self.assertIsNone(t3.ambiguity_reason)
        self.assertEqual(t3.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t3.emergency_level)
        self.assertIsNone(t3.dosage)

        # 4. Increase my blood pressure medicine... (unauthorized dose change request)
        t4_tasks = PlanWorkflow.extract_tasks_from_text("k4", "Increase my blood pressure medicine dose because my reading is high.")
        self.assertEqual(len(t4_tasks), 1)
        t4 = t4_tasks[0]
        self.assertTrue(t4.is_ambiguous)
        self.assertEqual(t4.emergency_level, SafetyEmergencyLevel.CLINICAL_BLOCK)
        self.assertIn("CLINICAL SAFETY BLOCK", t4.ambiguity_reason)
        self.assertIn("dosage change", t4.ambiguity_reason.lower())
        self.assertEqual(t4.confirmation_status, ConfirmationStatus.AMBIGUOUS)

        # 5. If a dose is missed, contact the treating clinician... (clinician contact / follow-up)
        t5_tasks = PlanWorkflow.extract_tasks_from_text("k5", "If a dose is missed, contact the treating clinician for guidance.")
        self.assertEqual(len(t5_tasks), 1)
        t5 = t5_tasks[0]
        self.assertEqual(t5.category, TaskCategory.FOLLOW_UP)
        self.assertFalse(t5.is_ambiguous)
        self.assertIsNone(t5.ambiguity_reason)
        self.assertEqual(t5.confirmation_status, ConfirmationStatus.PROPOSED)
        self.assertIsNone(t5.emergency_level)
        self.assertIsNone(t5.dosage)

    def test_l_synthetic_test_009_discrepancy_regression(self):
        """L. Regression test for SYNTHETIC-TEST-009:
        Verifies exact task extraction, exclusion of metadata, proposed tasks,
        and identifies the exact instruction contributing to the ambiguity count.
        """
        plan_text = """1. The patient does not report difficulty breathing.
2. Do not stop taking prescribed medication without consulting the treating clinician.
3. Do not increase the prescribed dose without clinician approval.
4. If a dose is missed, contact the treating clinician or pharmacist for guidance.
5. The patient reports sudden severe chest pain and difficulty breathing.
6. Record the patient's symptoms and inform the treating clinician.

Reference: SYNTHETIC-TEST-009
Clinician: Dr. Test Clinician"""
        res = PlanWorkflow.process_new_care_plan(
            plan_id="plan_reg_009",
            synthetic_patient_id="PAT-009",
            patient_name="Synthetic Patient 009",
            doctor_name="Dr. Test Clinician",
            diagnosis_context="Post-Op Recovery & Symptom Check",
            source_text=plan_text
        )

        # 1. Total extracted care tasks must be exactly 6 (metadata excluded)
        self.assertEqual(res["total_tasks"], 6)
        tasks = res["tasks"]
        task_texts = [t["instruction_text"] for t in tasks]
        self.assertNotIn("Reference: SYNTHETIC-TEST-009", task_texts)
        self.assertNotIn("Clinician: Dr. Test Clinician", task_texts)

        # 2. Emergency red flag is properly detected on Task 5
        self.assertTrue(res["emergency_detected"])
        self.assertEqual(tasks[4]["emergency_level"], SafetyEmergencyLevel.EMERGENCY.value if hasattr(SafetyEmergencyLevel.EMERGENCY, "value") else "emergency")
        self.assertIn("severe chest pain", tasks[4]["instruction_text"])

        # 3. Tasks 1, 2, 3, 4, 6 are non-ambiguous proposed tasks
        for idx in [0, 1, 2, 3, 5]:
            self.assertFalse(tasks[idx]["is_ambiguous"], f"Task {idx+1} should not be ambiguous")
            self.assertEqual(tasks[idx]["confirmation_status"], ConfirmationStatus.PROPOSED.value if hasattr(ConfirmationStatus.PROPOSED, "value") else "proposed")

        # 4. Task 5 is the sole contributor to ambiguous_tasks count
        self.assertEqual(res["ambiguous_tasks"], 1)
        self.assertEqual(res["proposed_tasks"], 5)
        self.assertTrue(tasks[4]["is_ambiguous"])
        self.assertIn("EMERGENCY RED FLAG", tasks[4]["ambiguity_reason"])


if __name__ == "__main__":
    unittest.main()
