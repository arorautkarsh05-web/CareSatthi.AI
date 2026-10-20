"""Interactive Command Line Interface (CLI) for CareSaathi AI.
Follows the Demo Script from PRD Section 15 and allows interactive testing.
"""
import sys
import time
from caresaathi.orchestrator import CareSaathiOrchestrator
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.routine_workflow import RoutineWorkflow
from caresaathi.monitoring_workflow import MonitoringWorkflow
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.report_workflow import ReportWorkflow
from caresaathi.agent import get_agent_info
from synthetic_data.sample_plans import SAMPLE_PLANS, SAFETY_TEST_CASES


def print_banner():
    print("""
===================================================================
   CareSaathi AI - Doctor-Guided Home Care Coordination Agent
   Fetch-A-Thon 3.0 | GCET Edition | Version 1.0
   Fetch.ai uAgent: Traceable Care-to-Action Architecture
===================================================================
    """)


def run_automated_demo():
    """Executes the complete 3-minute hackathon demo script sequentially."""
    print_banner()
    orch = CareSaathiOrchestrator()
    patient_id = "PATIENT_RAMESH_62"

    print("\n--- STEP 1: Demonstrating Fictional Care Plan Ingestion & Extraction (FR-01, FR-02) ---")
    plan_data = SAMPLE_PLANS["cardiac_recovery"]
    print(f"Patient: {plan_data['patient_name']} | Diagnosis: {plan_data['diagnosis']}")
    print(f"Doctor: {plan_data['doctor_name']}")
    print("\nExtracting structured tasks with direct source snippets...")
    plan_res = PlanWorkflow.process_new_care_plan(
        plan_id=plan_data["plan_id"],
        synthetic_patient_id=patient_id,
        patient_name=plan_data["patient_name"],
        doctor_name=plan_data["doctor_name"],
        diagnosis_context=plan_data["diagnosis"],
        source_text=plan_data["text"]
    )
    print(f"-> Extracted {plan_res['total_tasks']} tasks. All currently in 'PROPOSED' state.")
    for t in plan_res["tasks"][:4]:
        print(f"   [PROPOSED] {t['task_id']} | {t['scheduled_time_if_explicit'] or 'Anytime'}: {t['instruction_text']}")
        print(f"              Source reference: \"{t['source_reference']}\"")

    print("\n--- STEP 2: Confirmation Gate & Daily Checklist Generation (FR-04, FR-05) ---")
    print("User reviews tasks against original doctor plan and confirms non-clinical formatting...")
    conf_res = PlanWorkflow.confirm_care_plan(plan_data["plan_id"])
    print(f"-> {conf_res['message']}")

    print("\nRetrieving today's chronological care checklist...")
    checklist_res = RoutineWorkflow.get_daily_checklist(patient_id)
    print(f"Active tasks scheduled for today ({checklist_res['date']}):")
    for item in checklist_res["checklist"][:5]:
        print(f"   [{item['status'].upper()}] {item['task_id']} ({item['scheduled_time']}) - {item['instruction_text']}")

    print("\n--- STEP 3: Task Status Update & Immutable Audit Trail (FR-05, FR-06) ---")
    task_to_update = checklist_res["checklist"][0]["task_id"]
    print(f"Marking task {task_to_update} as COMPLETED with caregiver note...")
    update_res = RoutineWorkflow.update_task_status(
        task_id=task_to_update,
        new_status="completed",
        optional_note="Given at 08:00 AM after breakfast with water. Patient feeling comfortable."
    )
    print(f"-> Status change recorded: {update_res['previous_status']} -> {update_res['new_status']} at {update_res['timestamp']}")
    print(f"   Audit Trail confirmed for: \"{update_res['source_reference']}\"")

    print("\n--- STEP 4: Patient-Reported Symptom & Vitals Logging (FR-07) ---")
    print("Caregiver logs morning blood pressure observation...")
    sym_res = MonitoringWorkflow.log_symptom(
        synthetic_patient_id=patient_id,
        description="Routine morning resting blood pressure check",
        optional_reading=126.0,
        unit_if_provided="mmHg (Systolic)",
        reading_type="blood_pressure"
    )
    print(f"-> Entry saved as '{sym_res['source_label']}'. Reading: {sym_res['reading']}")
    print(f"   Safety Level: {sym_res['emergency_level']}. No diagnosis inferred.")

    print("\n--- STEP 5: Ambiguity Handling & Zero Hallucination (FR-03) ---")
    amb_data = SAMPLE_PLANS["ambiguous_test_plan"]
    print(f"Submitting care plan with intentionally ambiguous instructions ('{amb_data['diagnosis']}')...")
    amb_res = PlanWorkflow.process_new_care_plan(
        plan_id=amb_data["plan_id"],
        synthetic_patient_id=amb_data["patient_id"],
        patient_name=amb_data["patient_name"],
        doctor_name=amb_data["doctor_name"],
        diagnosis_context=amb_data["diagnosis"],
        source_text=amb_data["text"]
    )
    print(f"-> Ambiguities detected: {amb_res['ambiguous_tasks']}/{amb_res['total_tasks']} tasks.")
    for t in amb_res["tasks"]:
        if t["is_ambiguous"]:
            print(f"   [FLAGGED AMBIGUOUS] \"{t['instruction_text']}\"")
            print(f"                       Reason: {t['ambiguity_reason']}")
            print(f"                       Action: Never guessed! Sent to unresolved questions.")

    print("\n--- STEP 6: Deterministic Safety Guardrails & Emergency Handling (FR-08) ---")
    print("Testing 1: Acute Emergency Red Flag (Chest Pain)...")
    emer_test = orch.process_message(
        "I am feeling sudden severe crushing chest pain radiating to my left arm.",
        patient_id=patient_id
    )
    print(f"-> Trigger Result: {emer_test['intent']} (Emergency Contact: {emer_test['emergency_contact']})")
    print(f"   Response: {emer_test['message']}")

    print("\nTesting 2: Clinical Boundary Block (Discontinue Medication)...")
    block_test = orch.process_message(
        "Can I stop taking my blood thinner (Aspirin)?",
        patient_id=patient_id
    )
    print(f"-> Safety Intervention: {block_test['status'].upper()}")
    print(f"   Response: {block_test['message']}")

    print("\n--- STEP 7: Clinician-Ready Progress Report Generation (FR-09) ---")
    print("Generating comprehensive progress report for treating clinician...")
    rep_res = ReportWorkflow.generate_progress_report(patient_id, days_back=7)
    print(f"-> Report compiled. Adherence Rate: {rep_res['adherence_rate']}%")
    print(f"   Active Tasks: {rep_res['task_counts']['total']} | Symptoms: {rep_res['total_symptoms']} | Unresolved Questions: {rep_res['unresolved_questions_count']}")
    print("\n--- EXCERPT OF CLINICIAN REPORT ---")
    lines = rep_res["report_markdown"].splitlines()
    for l in lines[:24]:
        print(l)
    print("... [Complete report available in Web Dashboard / Export] ...")

    print("\n--- STEP 8: Fetch.ai uAgent Identity & Verification (FR-10) ---")
    agent_info = get_agent_info()
    print(f"Agent Name:    {agent_info['name']}")
    print(f"Agent Address: {agent_info['address']}")
    print(f"Endpoint:      {agent_info['endpoint']}")
    print(f"Protocols:     {agent_info['protocols']}")
    print(f"Live Tools:    {agent_info['tools']}")

    print("\n===================================================================")
    print("   END-TO-END DEMO JOURNEY COMPLETED SUCCESSFULLY!")
    print("===================================================================\n")


if __name__ == "__main__":
    run_automated_demo()
