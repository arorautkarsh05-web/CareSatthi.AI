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

    def test_05_request_response_message_passing_cycle(self):
        """Task 1 Integration Test: Proves genuine request-response cycle across agent communication handlers."""
        import asyncio
        import logging
        from caresaathi.multi_agent import (
            handle_safety_verification, handle_safety_response,
            multi_agent_audit_log, clear_multi_agent_cache
        )

        clear_multi_agent_cache()

        class MockAgentContext:
            def __init__(self):
                self.sent_messages = []
                self.logger = logging.getLogger("MockAgentContext")

            async def send(self, destination: str, message):
                self.sent_messages.append({"destination": destination, "message": message})

        async def run_cycle():
            orch_ctx = MockAgentContext()
            safety_ctx = MockAgentContext()

            orch_addr = str(orchestrator_agent.address)
            safety_addr = str(safety_agent.address)

            # 1. Orchestrator creates and dispatches structured request to Safety Guardian
            req = SafetyVerificationRequest(
                query_text="Can I double my ramipril dose to 10mg?",
                patient_id="PATIENT-TEST-01",
                request_id="req_cycle_001"
            )

            # 2. Safety Guardian specialist receives, evaluates, and sends response back
            await handle_safety_verification(safety_ctx, orch_addr, req)

            # Assert Safety Guardian dispatched response to Orchestrator address
            self.assertEqual(len(safety_ctx.sent_messages), 1)
            dispatched = safety_ctx.sent_messages[0]
            self.assertEqual(dispatched["destination"], orch_addr)
            response_msg = dispatched["message"]
            self.assertIsInstance(response_msg, SafetyVerificationResponse)
            self.assertFalse(response_msg.is_safe)
            self.assertEqual(response_msg.scenario_code, "BLOCK_CHANGE_DOSAGE")

            # 3. Orchestrator receives response from Safety Guardian
            await handle_safety_response(orch_ctx, safety_addr, response_msg)

            # 4. Verify Orchestrator recorded the verified response in audit trail
            self.assertEqual(len(multi_agent_audit_log), 1)
            audit_record = multi_agent_audit_log[0]
            self.assertEqual(audit_record["from"], safety_addr)
            self.assertEqual(audit_record["data"]["request_id"], "req_cycle_001")
            self.assertEqual(audit_record["data"]["scenario_code"], "BLOCK_CHANGE_DOSAGE")

        asyncio.run(run_cycle())

    def test_06_request_deduplication_prevents_duplicate_processing(self):
        """Task 1 & 6: Duplicate requests with same request_id are deduplicated via cache."""
        import asyncio
        import logging
        from caresaathi.multi_agent import (
            handle_safety_verification, clear_multi_agent_cache, PROCESSED_REQUEST_CACHE
        )

        clear_multi_agent_cache()

        class MockAgentContext:
            def __init__(self):
                self.sent_messages = []
                self.logger = logging.getLogger("MockAgentContext")

            async def send(self, destination: str, message):
                self.sent_messages.append({"destination": destination, "message": message})

        async def run_dedup():
            ctx = MockAgentContext()
            req = SafetyVerificationRequest(
                query_text="Severe crushing chest pain",
                request_id="req_dedup_099"
            )

            # First invocation
            await handle_safety_verification(ctx, "agent1_caller", req)
            self.assertEqual(len(ctx.sent_messages), 1)
            self.assertIn("req_dedup_099", PROCESSED_REQUEST_CACHE)

            # Second duplicate invocation
            await handle_safety_verification(ctx, "agent1_caller", req)
            self.assertEqual(len(ctx.sent_messages), 2)
            # Response must be identical cached response
            self.assertEqual(ctx.sent_messages[0]["message"].message, ctx.sent_messages[1]["message"].message)

        asyncio.run(run_dedup())


if __name__ == "__main__":
    unittest.main()
