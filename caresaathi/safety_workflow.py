"""Safety Workflow / Safety Agent for CareSaathi AI.
Enforces deterministic safety policies, clinical boundaries, and emergency escalations.
Strictly conforms to PRD Section 8 and FR-08.
"""
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from caresaathi.config import NATIONAL_EMERGENCY_NUMBER, AMBULANCE_NUMBER
from caresaathi.models import SafetyEmergencyLevel, SafetyEvent
from caresaathi.db import save_safety_event


# Emergency Red Flag Keywords & Scenarios
# In India, 112 is the national emergency number
EMERGENCY_SCENARIOS = [
    {
        "code": "EMERGENCY_CHEST_PAIN",
        "keywords": [r"chest pain", r"pain in chest", r"chest pressure", r"tightness in chest", r"crushing chest", r"pain radiating to (?:arm|jaw|back)"],
        "message": (
            f"URGENT EMERGENCY ALERT: Your reported symptoms indicate potential acute cardiac distress. "
            f"Please stop all activity and CALL {NATIONAL_EMERGENCY_NUMBER} (National Emergency) or {AMBULANCE_NUMBER} (Ambulance) IMMEDIATELY. "
            "Do not wait for further chat replies or delay seeking emergency medical attention."
        )
    },
    {
        "code": "EMERGENCY_SEVERE_DYSPNEA",
        "keywords": [r"severe shortness of breath", r"can't breathe", r"struggling to breathe", r"gasping for air", r"choking", r"blue lips"],
        "message": (
            f"URGENT EMERGENCY ALERT: Severe respiratory distress detected. "
            f"Please CALL {NATIONAL_EMERGENCY_NUMBER} or go to the nearest emergency department IMMEDIATELY. "
            "Do not attempt home remedies or delay emergency assistance."
        )
    },
    {
        "code": "EMERGENCY_STROKE_SIGNS",
        "keywords": [r"face droop", r"arm weakness", r"slurred speech", r"sudden numbness", r"sudden paralysis", r"loss of balance"],
        "message": (
            f"URGENT EMERGENCY ALERT: Sudden neurological symptoms observed (possible stroke signs). "
            f"Time is critical. Please CALL {NATIONAL_EMERGENCY_NUMBER} or proceed to an emergency stroke center IMMEDIATELY."
        )
    },
    {
        "code": "EMERGENCY_ANAPHYLAXIS",
        "keywords": [r"swollen throat", r"tongue swelling", r"throat closing", r"anaphylaxis", r"severe allergic reaction"],
        "message": (
            f"URGENT EMERGENCY ALERT: Possible severe allergic reaction / airway obstruction. "
            f"If an epinephrine auto-injector was prescribed, administer it now and CALL {NATIONAL_EMERGENCY_NUMBER} IMMEDIATELY."
        )
    },
    {
        "code": "EMERGENCY_SEVERE_BLEEDING",
        "keywords": [r"severe bleeding", r"blood won't stop", r"coughing up blood", r"vomiting blood", r"black tarry stool"],
        "message": (
            f"URGENT EMERGENCY ALERT: Acute heavy bleeding or hemorrhage reported. "
            f"Apply direct firm pressure to visible wounds and CALL {NATIONAL_EMERGENCY_NUMBER} IMMEDIATELY."
        )
    },
    {
        "code": "EMERGENCY_LOSS_OF_CONSCIOUSNESS",
        "keywords": [r"fainted", r"passed out", r"loss of consciousness", r"unresponsive"],
        "message": (
            f"URGENT EMERGENCY ALERT: Loss of consciousness or unresponsiveness reported. "
            f"Ensure the person is lying safely on their side and CALL {NATIONAL_EMERGENCY_NUMBER} IMMEDIATELY."
        )
    }
]

# Clinical Boundary Violations (Actions forbidden by PRD Section 2.4 and 8)
CLINICAL_BOUNDARY_PATTERNS = [
    {
        "code": "BLOCK_CHANGE_DOSAGE",
        "pattern": r"\b(?:increase|decrease|double|halve|cut in half|change|modify|adjust|take 2|take two)\s+(?:the\s+|my\s+)?(?:[a-z0-9\-]+\s+)?(?:dose|dosage|amount|milligrams|mg|tablets?|pills?)",
        "message": (
            "SAFETY POLICY BLOCK: CareSaathi AI is strictly prohibited from modifying medication dosages. "
            "Changing doses without medical supervision can lead to toxicity or therapeutic failure. "
            "Please consult your treating doctor or pharmacist before making any dosage changes."
        )
    },
    {
        "code": "BLOCK_STOP_MEDICATION",
        "pattern": r"\b(?:(?:can i|should i|want to|shall i)\s+(?:stop|discontinue|quit|hold|pause|skip)|stop\s+taking|discontinue|quit\s+taking)\s*(?:the\s+|my\s+)?(?:[a-z0-9\-]+\s+)?(?:tablet|medication|medicine|pill|dose|aspirin|metformin|statin|insulin|blood thinner|antibiotic)?",
        "message": (
            "SAFETY POLICY BLOCK: CareSaathi AI cannot advise you to discontinue, stop, or pause any prescribed medication. "
            "Medication changes must only be approved by your treating clinician. "
            "We have logged this inquiry as an unresolved question in your clinician report so you can discuss it safely at your next consult."
        )
    },
    {
        "code": "BLOCK_DIAGNOSIS_REQUEST",
        "pattern": r"\b(?:do i have|could this be|diagnose|what disease|is this (?:a heart attack|cancer|infection|covid|diabetes|stroke))",
        "message": (
            "SAFETY POLICY BLOCK: CareSaathi AI is a care coordination agent, not a diagnostic medical system. "
            "It cannot diagnose medical conditions or rule out illnesses. "
            "Your symptoms have been logged as 'patient-reported' and added to your progress summary for your doctor."
        )
    },
    {
        "code": "BLOCK_PRESCRIBE_NEW",
        "pattern": r"\b(?:what (?:medicine|pill|tablet|drug) should i take|prescribe|recommend a (?:medicine|cure|remedy))",
        "message": (
            "SAFETY POLICY BLOCK: CareSaathi AI cannot prescribe, suggest, or recommend new medications or treatments. "
            "Only your registered healthcare practitioner can prescribe medications based on clinical evaluation."
        )
    }
]


class SafetyWorkflow:
    """Specialist workflow for deterministic safety enforcement and clinical guardrails."""

    @staticmethod
    def evaluate_text_safety(text: str) -> Dict[str, Any]:
        """Evaluates arbitrary user input against emergency red flags and clinical boundary blocks."""
        lower = text.lower()

        # 1. Check for life-threatening emergency scenarios first
        for scenario in EMERGENCY_SCENARIOS:
            for kw in scenario["keywords"]:
                if re.search(kw, lower):
                    event = SafetyEvent(
                        event_id=f"safe_{int(datetime.now().timestamp() * 1000)}",
                        scenario_code=scenario["code"],
                        triggered_at=datetime.now().isoformat(),
                        trigger_text=text,
                        action_taken="Emergency Escalation Triggered",
                        emergency_level=SafetyEmergencyLevel.EMERGENCY,
                        rule_version="1.0.0",
                        acknowledged_status=False,
                        emergency_contact_number=NATIONAL_EMERGENCY_NUMBER
                    )
                    save_safety_event(event)

                    return {
                        "is_safe": False,
                        "emergency_level": SafetyEmergencyLevel.EMERGENCY.value,
                        "scenario_code": scenario["code"],
                        "emergency_contact": NATIONAL_EMERGENCY_NUMBER,
                        "message": scenario["message"],
                        "requires_immediate_action": True
                    }

        # 2. Check for clinical boundary violations
        for boundary in CLINICAL_BOUNDARY_PATTERNS:
            if re.search(boundary["pattern"], lower):
                event = SafetyEvent(
                    event_id=f"safe_{int(datetime.now().timestamp() * 1000)}",
                    scenario_code=boundary["code"],
                    triggered_at=datetime.now().isoformat(),
                    trigger_text=text,
                    action_taken="Clinical Boundary Block Enforced",
                    emergency_level=SafetyEmergencyLevel.CLINICAL_BLOCK,
                    rule_version="1.0.0",
                    acknowledged_status=True,
                    emergency_contact_number=None
                )
                save_safety_event(event)

                return {
                    "is_safe": False,
                    "emergency_level": SafetyEmergencyLevel.CLINICAL_BLOCK.value,
                    "scenario_code": boundary["code"],
                    "emergency_contact": None,
                    "message": boundary["message"],
                    "requires_immediate_action": False
                }

        return {
            "is_safe": True,
            "emergency_level": SafetyEmergencyLevel.NORMAL.value,
            "scenario_code": None,
            "emergency_contact": None,
            "message": "Passed deterministic safety screening."
        }

    @staticmethod
    def evaluate_vital_reading(reading_type: str, value: float) -> Tuple[SafetyEmergencyLevel, Optional[str]]:
        """Evaluates numerical vitals with standard clinical safety thresholds."""
        r_type = reading_type.lower()

        # Blood pressure systolic check
        if "systolic" in r_type or "bp" in r_type:
            if value >= 180:
                return (
                    SafetyEmergencyLevel.EMERGENCY,
                    f"CRITICAL WARNING: Blood pressure reading of {value} mmHg indicates a potential hypertensive crisis. If accompanied by headache, chest pain, or vision changes, CALL {NATIONAL_EMERGENCY_NUMBER} immediately."
                )
            elif value >= 140:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"Elevated blood pressure ({value} mmHg). Recorded as patient-reported reading for clinician review."
                )
            elif value < 90:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"Low blood pressure ({value} mmHg). If feeling dizzy or lightheaded, sit down safely and hydrate."
                )

        # Blood glucose check
        if "glucose" in r_type or "sugar" in r_type:
            if value < 60:
                return (
                    SafetyEmergencyLevel.EMERGENCY,
                    f"CRITICAL ALERT: Blood glucose of {value} mg/dL indicates hypoglycemia. Consume 15g fast-acting sugar (fruit juice or glucose tablets) immediately. If confusion or lethargy occurs, seek emergency care."
                )
            elif value > 300:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"High blood glucose reading ({value} mg/dL). Ensure prescribed hydration and notify clinician if persistent ketones or symptoms occur."
                )

        # SpO2 (Oxygen saturation)
        if "spo2" in r_type or "oxygen" in r_type:
            if value < 92:
                return (
                    SafetyEmergencyLevel.EMERGENCY,
                    f"CRITICAL ALERT: Oxygen saturation of {value}% is below normal threshold. If experiencing shortness of breath, CALL {NATIONAL_EMERGENCY_NUMBER} immediately."
                )

        # Temperature
        if "temp" in r_type:
            if value >= 103.0:
                return (
                    SafetyEmergencyLevel.WARNING,
                    f"High temperature ({value}°F). Recorded as patient-reported symptom. Contact clinician if fever fails to respond to prescribed care plan."
                )

        return SafetyEmergencyLevel.NORMAL, None
