"""Fetch.ai uAgent implementation for CareSaathi AI.
Provides:
1. Agentverse registration & discovery capability.
2. Structured message protocol (CareSaathiCoordinationProtocol).
3. Real state-changing tool actions (FR-10).
4. Report generation tool action (FR-10).
Follows PRD Section 6.4 strictly.
"""
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from uagents import Agent, Context, Model, Protocol
from caresaathi.config import AGENT_NAME, AGENT_SEED, AGENT_PORT, AGENT_ENDPOINT
from caresaathi.orchestrator import CareSaathiOrchestrator
from caresaathi.plan_workflow import PlanWorkflow
from caresaathi.routine_workflow import RoutineWorkflow
from caresaathi.monitoring_workflow import MonitoringWorkflow
from caresaathi.report_workflow import ReportWorkflow
from caresaathi.safety_workflow import SafetyWorkflow


# UAgents Message Models
class CareSaathiRequest(Model):
    message: str
    patient_id: str = "Demo-Patient-01"
    action: Optional[str] = None  # None for natural language, or explicit tool action name
    payload: Optional[Dict[str, Any]] = None


class CareSaathiResponse(Model):
    intent: str
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    emergency_level: Optional[str] = None
    timestamp: str


# Initialize CareSaathi uAgent
agent = Agent(
    name=AGENT_NAME,
    seed=AGENT_SEED,
    port=AGENT_PORT,
    endpoint=[AGENT_ENDPOINT],
)

# CareSaathi Protocol
caresathi_protocol = Protocol(
    name="CareSaathiCoordinationProtocol",
    version="1.0.0"
)

orchestrator = CareSaathiOrchestrator()


@agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info("=====================================================")
    ctx.logger.info(f"CareSaathi AI uAgent Started successfully!")
    ctx.logger.info(f"Agent Name:    {agent.name}")
    ctx.logger.info(f"Agent Address: {agent.address}")
    ctx.logger.info(f"Endpoint:      {AGENT_ENDPOINT}")
    ctx.logger.info(f"Protocol:      CareSaathiCoordinationProtocol v1.0.0")
    ctx.logger.info("Ready to coordinate doctor-guided care plans.")
    ctx.logger.info("=====================================================")


@caresathi_protocol.on_message(model=CareSaathiRequest, replies=CareSaathiResponse)
async def message_handler(ctx: Context, sender: str, msg: CareSaathiRequest):
    ctx.logger.info(f"Received message from {sender}: {msg.message[:80]}...")

    # FR-10: Support real state-changing tool actions directly or via natural language orchestrator
    if msg.action:
        ctx.logger.info(f"Executing explicit tool action: {msg.action}")
        result = execute_agent_tool(msg.action, msg.payload or {}, msg.patient_id)
        response = CareSaathiResponse(
            intent=msg.action,
            status=result.get("status", "success"),
            message=result.get("message", "Tool executed successfully."),
            data=result.get("data", result),
            emergency_level=result.get("emergency_level"),
            timestamp=datetime.now().isoformat()
        )
    else:
        # Route through natural language orchestrator
        orch_result = orchestrator.process_message(
            user_message=msg.message,
            patient_id=msg.patient_id,
            context=msg.payload
        )
        response = CareSaathiResponse(
            intent=orch_result.get("intent", "UNKNOWN"),
            status=orch_result.get("status", "success"),
            message=orch_result.get("message", ""),
            data=orch_result.get("data"),
            emergency_level=orch_result.get("emergency_level"),
            timestamp=datetime.now().isoformat()
        )

    await ctx.send(sender, response)


# Register protocol with agent
agent.include(caresathi_protocol)


def execute_agent_tool(action: str, payload: Dict[str, Any], patient_id: str) -> Dict[str, Any]:
    """FR-10: Executes real state-changing or report-generating tool actions."""
    action_lower = action.lower()

    try:
        if action_lower == "set_care_plan":
            plan_id = payload.get("plan_id", f"plan_{int(datetime.now().timestamp() * 1000)}")
            return PlanWorkflow.process_new_care_plan(
                plan_id=plan_id,
                synthetic_patient_id=patient_id,
                patient_name=payload.get("patient_name", "Synthetic Patient"),
                doctor_name=payload.get("doctor_name", "Dr. Mehta, MD"),
                diagnosis_context=payload.get("diagnosis", "Post-Discharge Recovery"),
                source_text=payload.get("source_text", "")
            )

        elif action_lower == "confirm_care_plan":
            plan_id = payload.get("plan_id")
            return PlanWorkflow.confirm_care_plan(plan_id, payload.get("task_ids"))

        elif action_lower == "get_daily_checklist":
            return RoutineWorkflow.get_daily_checklist(patient_id)

        elif action_lower == "update_task_status":
            return RoutineWorkflow.update_task_status(
                task_id=payload.get("task_id", ""),
                new_status=payload.get("status", "completed"),
                optional_note=payload.get("note")
            )

        elif action_lower == "log_symptom":
            return MonitoringWorkflow.log_symptom(
                synthetic_patient_id=patient_id,
                description=payload.get("description", ""),
                optional_reading=payload.get("reading"),
                unit_if_provided=payload.get("unit"),
                reading_type=payload.get("reading_type")
            )

        elif action_lower == "generate_progress_report":
            return ReportWorkflow.generate_progress_report(
                synthetic_patient_id=patient_id,
                days_back=payload.get("days_back", 7)
            )

        elif action_lower == "evaluate_safety":
            return SafetyWorkflow.evaluate_text_safety(payload.get("text", ""))

        else:
            return {
                "status": "error",
                "message": f"Unknown tool action '{action}'. Available: set_care_plan, confirm_care_plan, get_daily_checklist, update_task_status, log_symptom, generate_progress_report, evaluate_safety."
            }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Tool execution failed for '{action}': {str(exc)}"
        }


def get_agent_info() -> Dict[str, Any]:
    """Returns agent identity, address, and metadata for Agentverse discovery."""
    return {
        "name": agent.name,
        "address": str(agent.address),
        "endpoint": AGENT_ENDPOINT,
        "protocols": ["CareSaathiCoordinationProtocol v1.0.0"],
        "tools": [
            "set_care_plan", "confirm_care_plan", "get_daily_checklist",
            "update_task_status", "log_symptom", "generate_progress_report", "evaluate_safety"
        ],
        "status": "active"
    }


if __name__ == "__main__":
    print(f"Starting CareSaathi AI Fetch.ai uAgent on address: {agent.address}...")
    agent.run()
