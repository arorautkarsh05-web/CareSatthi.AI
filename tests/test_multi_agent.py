"""Tests for the optional Fetch.ai Multi-Agent Bureau architecture.
Validates multi-agent initialization, protocol structures, and specialist behavior.
"""
import unittest
from caresaathi.multi_agent import (
    orchestrator_agent, safety_agent, plan_agent,
    create_multi_agent_bureau, get_multi_agent_specs,
    SafetyVerificationRequest, SafetyVerificationResponse,
    PlanExtractionRequest, PlanExtractionResponse
)
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.plan_workflow import PlanWorkflow


class TestCareSaathiMultiAgent(unittest.TestCase):

    def test_01_agent_identities_and_addresses(self):
        """Verify each specialist agent has a valid and distinct Bech32 address."""
        specs = get_multi_agent_specs()
        agents = specs["agents"]
        self.assertEqual(len(agents), 3)

        addresses = [a["address"] for a in agents]
        self.assertEqual(len(set(addresses)), 3, "Agent addresses must be unique")
        for addr in addresses:
            self.assertTrue(addr.startswith("agent1"), f"Invalid Bech32 address: {addr}")

    def test_02_protocol_message_models(self):
        """Verify request and response Pydantic models for agent-to-agent communication."""
        # Safety Request & Response
        req = SafetyVerificationRequest(query_text="Can I double my dose?", request_id="req_001")
        self.assertEqual(req.query_text, "Can I double my dose?")

        eval_res = SafetyWorkflow.evaluate_text_safety(req.query_text)
        resp = SafetyVerificationResponse(
            request_id=req.request_id,
            is_safe=eval_res["is_safe"],
            emergency_level=eval_res["emergency_level"],
            scenario_code=eval_res["scenario_code"],
            message=eval_res["message"]
        )
        self.assertFalse(resp.is_safe)
        self.assertEqual(resp.scenario_code, "BLOCK_CHANGE_DOSAGE")
        self.assertEqual(resp.emergency_level, "clinical_block")

    def test_03_plan_specialist_protocol_models(self):
        """Verify plan specialist request and response models."""
        plan_req = PlanExtractionRequest(
            plan_id="multi_plan_001",
            patient_id="PATIENT_MULTI_01",
            patient_name="Multi Agent Patient",
            doctor_name="Dr. Multi",
            diagnosis="Post-Op Recovery",
            source_text="1. Tab Aspirin 75mg once daily at 08:00 AM after breakfast.\n2. Walk 15 minutes.",
            request_id="plan_req_001"
        )
        self.assertEqual(plan_req.plan_id, "multi_plan_001")

        res = PlanWorkflow.process_new_care_plan(
            plan_id=plan_req.plan_id,
            synthetic_patient_id=plan_req.patient_id,
            patient_name=plan_req.patient_name,
            doctor_name=plan_req.doctor_name,
            diagnosis_context=plan_req.diagnosis,
            source_text=plan_req.source_text
        )
        plan_resp = PlanExtractionResponse(
            request_id=plan_req.request_id,
            status=res["status"],
            total_tasks=res["total_tasks"],
            proposed_tasks=res["proposed_tasks"],
            ambiguous_tasks=res["ambiguous_tasks"],
            message=res["message"]
        )
        self.assertEqual(plan_resp.status, "success")
        self.assertEqual(plan_resp.total_tasks, 2)
        self.assertEqual(plan_resp.ambiguous_tasks, 0)

    def test_04_bureau_assembly(self):
        """Verify Bureau instance bundles all 3 agents without configuration errors."""
        bureau = create_multi_agent_bureau()
        self.assertIsNotNone(bureau)
        self.assertEqual(len(bureau._agents), 3)


if __name__ == "__main__":
    unittest.main()
