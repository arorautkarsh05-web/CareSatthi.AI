"""CareSaathi Multi-Agent Extension (Optional Bureau Implementation).
Demonstrates genuine message-passing communication across 3 specialist Fetch.ai uAgents:
1. CareSaathi Orchestrator Agent (Lead Coordinator)
2. Safety Guardian Specialist Agent (Clinical Guardrails & 112 Red Flags)
3. Care Plan Specialist Agent (Care-to-Action Extraction & Source Traceability)

Follows PRD Phase 6 and official Fetch.ai uAgents Bureau architecture.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from uagents import Agent, Bureau, Context, Model, Protocol
from caresaathi.safety_workflow import SafetyWorkflow
from caresaathi.plan_workflow import PlanWorkflow


# Message Models for genuine Agent-to-Agent Communication
class SafetyVerificationRequest(Model):
    query_text: str
    patient_id: str = "Demo-Patient-01"
    request_id: str


class SafetyVerificationResponse(Model):
    request_id: str
    is_safe: bool
    emergency_level: str
    scenario_code: str
    message: str
    emergency_contact: Optional[str] = None


class PlanExtractionRequest(Model):
    plan_id: str
    patient_id: str
    patient_name: str
    doctor_name: str
    diagnosis: str
    source_text: str
    request_id: str


class PlanExtractionResponse(Model):
    request_id: str
    status: str
    total_tasks: int
    proposed_tasks: int
    ambiguous_tasks: int
    message: str


# 1. Initialize Agents with deterministic seeds
orchestrator_agent = Agent(
    name="caresaathi_orchestrator",
    seed="caresaathi_orch_seed_2026_gcet",
    port=8020,
    endpoint=["http://127.0.0.1:8020/submit"]
)

safety_agent = Agent(
    name="caresaathi_safety_guardian",
    seed="caresaathi_safety_seed_2026_gcet",
    port=8021,
    endpoint=["http://127.0.0.1:8021/submit"]
)

plan_agent = Agent(
    name="caresaathi_plan_specialist",
    seed="caresaathi_plan_seed_2026_gcet",
    port=8022,
    endpoint=["http://127.0.0.1:8022/submit"]
)


# 2. Specialist Protocols
safety_protocol = Protocol(name="SafetyVerificationProtocol", version="1.0.0")
plan_protocol = Protocol(name="PlanSpecialistProtocol", version="1.0.0")
orchestrator_protocol = Protocol(name="OrchestratorProtocol", version="1.0.0")


# In-Memory request deduplication cache to prevent duplicate state changes
PROCESSED_REQUEST_CACHE: Dict[str, Any] = {}
multi_agent_audit_log = []


def clear_multi_agent_cache():
    """Resets cache and audit log for testing."""
    PROCESSED_REQUEST_CACHE.clear()
    multi_agent_audit_log.clear()


# --- Safety Specialist Agent Handlers ---
@safety_protocol.on_message(model=SafetyVerificationRequest, replies=SafetyVerificationResponse)
async def handle_safety_verification(ctx: Context, sender: str, msg: SafetyVerificationRequest):
    ctx.logger.info(f"[Safety Guardian] Received check from {sender} for request: {msg.request_id}")
    
    # Task 1 & 6: Deduplication check to prevent duplicate state mutation
    if msg.request_id in PROCESSED_REQUEST_CACHE:
        ctx.logger.info(f"[Safety Guardian] Duplicate request '{msg.request_id}' detected. Returning cached verification.")
        await ctx.send(sender, PROCESSED_REQUEST_CACHE[msg.request_id])
        return

    eval_result = SafetyWorkflow.evaluate_text_safety(msg.query_text)
    response = SafetyVerificationResponse(
        request_id=msg.request_id,
        is_safe=eval_result["is_safe"],
        emergency_level=eval_result["emergency_level"],
        scenario_code=eval_result.get("scenario_code", "NORMAL"),
        message=eval_result["message"],
        emergency_contact=eval_result.get("emergency_contact")
    )
    PROCESSED_REQUEST_CACHE[msg.request_id] = response
    ctx.logger.info(f"[Safety Guardian] Verification complete. is_safe={eval_result['is_safe']}, level={eval_result['emergency_level']}")
    await ctx.send(sender, response)


# --- Plan Specialist Agent Handlers ---
@plan_protocol.on_message(model=PlanExtractionRequest, replies=PlanExtractionResponse)
async def handle_plan_extraction(ctx: Context, sender: str, msg: PlanExtractionRequest):
    ctx.logger.info(f"[Plan Specialist] Received extraction request from {sender} for plan: {msg.plan_id}")
    
    # Task 1 & 6: Deduplication check to prevent duplicate plan persistence
    if msg.request_id in PROCESSED_REQUEST_CACHE:
        ctx.logger.info(f"[Plan Specialist] Duplicate plan request '{msg.request_id}' detected. Returning cached response.")
        await ctx.send(sender, PROCESSED_REQUEST_CACHE[msg.request_id])
        return

    res = PlanWorkflow.process_new_care_plan(
        plan_id=msg.plan_id,
        synthetic_patient_id=msg.patient_id,
        patient_name=msg.patient_name,
        doctor_name=msg.doctor_name,
        diagnosis_context=msg.diagnosis,
        source_text=msg.source_text
    )
    response = PlanExtractionResponse(
        request_id=msg.request_id,
        status=res.get("status", "success"),
        total_tasks=res.get("total_tasks", 0),
        proposed_tasks=res.get("proposed_tasks", 0),
        ambiguous_tasks=res.get("ambiguous_tasks", 0),
        message=res.get("message", "Tasks extracted successfully.")
    )
    PROCESSED_REQUEST_CACHE[msg.request_id] = response
    ctx.logger.info(f"[Plan Specialist] Extraction complete: {res.get('total_tasks', 0)} tasks extracted.")
    await ctx.send(sender, response)


# --- Orchestrator Protocol Handlers & Startup Event ---
@orchestrator_agent.on_event("startup")
async def orchestrator_startup_check(ctx: Context):
    """Dispatches a genuine startup safety verification request across the agent message bus."""
    ctx.logger.info(f"[Orchestrator] Dispatching initial safety handshake to Safety Guardian ({safety_agent.address})...")
    req = SafetyVerificationRequest(
        query_text="Startup system clinical boundary self-test",
        patient_id="System-Check",
        request_id=f"req_startup_{int(datetime.now().timestamp() * 1000)}"
    )
    await ctx.send(str(safety_agent.address), req)


@orchestrator_protocol.on_message(model=SafetyVerificationResponse)
async def handle_safety_response(ctx: Context, sender: str, msg: SafetyVerificationResponse):
    ctx.logger.info(f"[Orchestrator] Received Safety response from {sender}: {msg.scenario_code} - {msg.emergency_level}")
    multi_agent_audit_log.append({
        "timestamp": datetime.now().isoformat(),
        "from": sender,
        "type": "SafetyVerificationResponse",
        "data": msg.model_dump()
    })


@orchestrator_protocol.on_message(model=PlanExtractionResponse)
async def handle_plan_response(ctx: Context, sender: str, msg: PlanExtractionResponse):
    ctx.logger.info(f"[Orchestrator] Received Plan extraction response from {sender}: {msg.total_tasks} tasks")
    multi_agent_audit_log.append({
        "timestamp": datetime.now().isoformat(),
        "from": sender,
        "type": "PlanExtractionResponse",
        "data": msg.model_dump()
    })


# Attach protocols
safety_agent.include(safety_protocol)
plan_agent.include(plan_protocol)
orchestrator_agent.include(orchestrator_protocol)


def create_multi_agent_bureau() -> Bureau:
    """Builds a Fetch.ai Bureau containing all 3 specialist agents."""
    bureau = Bureau(port=8020)
    bureau.add(orchestrator_agent)
    bureau.add(safety_agent)
    bureau.add(plan_agent)
    return bureau


def get_multi_agent_specs() -> Dict[str, Any]:
    """Returns verifiable specs for all 3 communicating agents."""
    return {
        "architecture": "Fetch.ai Multi-Agent Bureau",
        "version": "1.0.0",
        "agents": [
            {
                "name": orchestrator_agent.name,
                "address": str(orchestrator_agent.address),
                "role": "Central Coordinator & Task Dispatcher",
                "port": 8020
            },
            {
                "name": safety_agent.name,
                "address": str(safety_agent.address),
                "role": "Safety Guardian Specialist (Emergency Escalation & Clinical Blocks)",
                "port": 8021
            },
            {
                "name": plan_agent.name,
                "address": str(plan_agent.address),
                "role": "Care Plan Specialist (Task Parsing & Source Quotation)",
                "port": 8022
            }
        ]
    }


if __name__ == "__main__":
    specs = get_multi_agent_specs()
    print("=" * 70)
    print("CareSaathi AI - Multi-Agent Specialist Bureau")
    print("=" * 70)
    for a in specs["agents"]:
        print(f"Agent: {a['name']:<28} Address: {a['address']}")
    print("=" * 70)
    print("Starting multi-agent Bureau cluster on ports 8020, 8021, 8022...")
    bureau = create_multi_agent_bureau()
    bureau.run()
