# CareSaathi AI 🩺
### Doctor-Guided Home Care Coordination Agent
**Fetch-A-Thon 3.0 | GCET Edition | Version 1.0**  
*Built with Fetch.ai `uagents`, FastAPI, and Deterministic Safety Guardrails*

---

## 🌟 Executive Summary
**CareSaathi AI** bridges the critical gap between receiving a doctor-approved care plan and reliably carrying it out at home. It empowers patients and family caregivers to organize instructions into a verified, trackable daily routine, logs patient-reported progress and vitals, deterministically blocks dangerous clinical boundary actions, and compiles a clinician-ready progress report.

CareSaathi is **not a diagnostic chatbot** and does **not prescribe, alter, or discontinue medical treatments**. Its core differentiator is the **Traceable Care-to-Action workflow**:
1. **Traceable by Default:** Every generated task is linked to an exact source quote from the doctor's plan.
2. **Confirmation Gate:** Tasks remain *proposed* until confirmed by the user.
3. **Zero-Hallucination Ambiguity Blocker:** Missing or vague instructions are never guessed; they are flagged as unresolved questions for the clinician.
4. **Deterministic Safety Policy:** Life-threatening emergencies trigger immediate instructions to call **112 (India National Emergency)** without chatbot delay.
5. **Real Fetch.ai uAgent Execution:** State-changing and report-generating tool execution with a verified Bech32 agent address.

---

## 🏛️ System Architecture

```
User / Caregiver (Web UI / CLI / Chat)
                    │
                    ▼
CareSaathi Fetch.ai uAgent (agent1q039k6qfpszyehmv67lwna03zqua086nnwym06reenzzksn99alqvrwdj5k)
                    │
                    ▼
CareSaathi Orchestrator (Intent Detection & Safety Pre-Screening)
                    │
   ┌────────────────┼────────────────┬────────────────┐
   ▼                ▼                ▼                ▼
Plan Workflow   Routine Workflow  Monitoring      Safety Workflow
(FR-01 - FR-04) (FR-05 - FR-06)   Workflow        (FR-08)
• Extraction    • Checklist       (FR-07)         • 112 Escalations
• Source Links  • Status Updates  • Patient Logs  • Clinical Blocks
• Ambiguities   • Audit Events    • Vital Checks  • Vitals Guardrails
   │                │                │                │
   └────────────────┴────────────────┴────────────────┘
                    │
                    ▼
          Report Workflow (FR-09)
          • Adherence Rate & Task History
          • Patient-Reported Symptoms & Vitals
          • Unresolved Clinical Questions
                    │
                    ▼
       SQLite ACID Storage (`data/caresaathi.db`)
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Git

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/CareSaathi-AI/CareSaathi.git
cd CareSaathi.AI

# Install required reproducible dependencies
pip install -r requirements.txt
```

### 3. Run the Automated End-to-End CLI Demo (3-minute Hackathon Script)
```powershell
python cli.py
```
This runs the complete user journey sequentially:
1. Ingests fictional Post-CABG recovery plan and extracts tasks with source links.
2. Passes Confirmation Gate and activates tasks.
3. Retrieves today's chronological care checklist.
4. Updates task status to `COMPLETED` with caregiver note and logs audit event.
5. Logs a patient-reported resting blood pressure observation.
6. Demonstrates zero-hallucination ambiguity detection on a vague plan.
7. Triggers deterministic safety checks (112 emergency alert & clinical block).
8. Generates the doctor-ready progress report.
9. Displays the verified Fetch.ai uAgent identity.

### 4. Run the Full Test Suite (19/19 Tests Passing)
```powershell
# Discover and run all 19 automated integration and safety tests
python -m unittest discover -s tests -v

# Or run separately:
python -m unittest tests/test_suite.py
python -m unittest tests/test_safety.py
```

### 5. Launch the Interactive Web Dashboard
```powershell
python run_server.py
```
Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** in your browser to access:
- **Care Plan Setup & Confirmation Gate:** Quick-load synthetic plans and inspect source quotes.
- **Daily Care Checklist:** Toggle task states, add notes, and track adherence in real-time.
- **Symptom & Vitals Log:** Record patient observations with immediate safety screening.
- **Deterministic Safety Sandbox:** Test red flags and clinical boundary blocks interactively.
- **Doctor Progress Report:** View and export clinician summaries.
- **Live Agent Chat:** Chat with the CareSaathi Orchestrator.
- **Fetch.ai Identity:** Inspect uAgent specifications and registered tool actions.

---

## 🤖 Fetch.ai uAgent Specifications

| Attribute | Value |
|---|---|
| **Agent Name** | `caresaathi_agent` |
| **Bech32 Address** | `agent1q039k6qfpszyehmv67lwna03zqua086nnwym06reenzzksn99alqvrwdj5k` |
| **Local Endpoint** | `http://127.0.0.1:8008/submit` |
| **Protocol** | `CareSaathiCoordinationProtocol v1.0.0` |
| **Supported Tools** | `set_care_plan`, `confirm_care_plan`, `get_daily_checklist`, `update_task_status`, `log_symptom`, `generate_progress_report`, `evaluate_safety` |
| **Integration Status** | ✅ Locally verified (Agent address, protocol, state-changing tools & unit tests) |

To run the standalone Fetch.ai agent listener:
```powershell
python caresaathi/agent.py
```

### Fetch.ai uAgent Integration Status
- **Implemented & Locally Tested:** Initialisation with deterministic seed, Bech32 address generation, typed protocol handlers (`CareSaathiRequest`, `CareSaathiResponse`), and 7 state-changing tools executed with SQLite transactional store.
- **Agentverse Registration (Cloud Discovery):** The uAgent can be linked to Agentverse Mailbox for global discoverability by setting `AGENT_MAILBOX_KEY` in environment variables. Local execution functions 100% offline without requiring external API keys.

---

## 🛡️ Safety & Clinical Guardrails (FR-08)

CareSaathi AI enforces strict, testable deterministic rules:

### 1. Life-Threatening Emergency Red Flags (India National Emergency: 112)
When keywords for acute distress (crushing chest pain, severe dyspnea, stroke signs FAST, anaphylaxis, severe hemorrhage) are detected:
- The system **immediately instructs the user to call 112** (or 102 for Ambulance).
- Further conversational delays or automated diagnoses are strictly prevented.

### 2. Prohibited Clinical Actions (Deterministic Blocks)
- **Stopping Medications:** Queries like *"Can I stop my blood thinner?"* are blocked. Patients are directed to discuss discontinuation with their prescribing doctor, and the inquiry is added to their progress report.
- **Modifying Dosages:** Requests to double or alter dosages are blocked to prevent medication toxicity.
- **Diagnostic Requests:** Queries asking the agent to diagnose an illness are blocked; symptoms are recorded solely as patient-reported observations.
- **Prescribing New Drugs:** The agent cannot recommend or prescribe new treatments.

### 3. Vitals Safety Thresholds
- **Blood Pressure Systolic >= 180 mmHg:** Triggers potential hypertensive crisis alert with 112 advisory if symptomatic.
- **Blood Glucose < 60 mg/dL:** Triggers immediate hypoglycemia guidance (consume 15g fast-acting sugar; seek emergency help if lethargic).
- **Oxygen Saturation SpO2 < 92%:** Triggers hypoxia warning.

---

## 📊 Functional Requirements Matrix (FR-01 to FR-12)

| Requirement | Description | Status | Implementation File |
|---|---|---|---|
| **FR-01** | Care-plan input | ✅ Passed | [`plan_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/plan_workflow.py) |
| **FR-02** | Structured extraction & source references | ✅ Passed | [`plan_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/plan_workflow.py) |
| **FR-03** | Ambiguity handling (no guessing) | ✅ Passed | [`plan_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/plan_workflow.py) |
| **FR-04** | Confirmation gate (proposed -> confirmed) | ✅ Passed | [`plan_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/plan_workflow.py) |
| **FR-05** | Daily care checklist (completed/skipped/delayed) | ✅ Passed | [`routine_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/routine_workflow.py) |
| **FR-06** | Task audit trail & event history | ✅ Passed | [`routine_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/routine_workflow.py), [`db.py`](file:///d:/CareSatthi.AI/caresaathi/db.py) |
| **FR-07** | Symptom log (labeled 'patient-reported') | ✅ Passed | [`monitoring_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/monitoring_workflow.py) |
| **FR-08** | Deterministic safety policy & 112 escalation | ✅ Passed | [`safety_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/safety_workflow.py) |
| **FR-09** | Clinician progress report | ✅ Passed | [`report_workflow.py`](file:///d:/CareSatthi.AI/caresaathi/report_workflow.py) |
| **FR-10** | Fetch.ai uAgent execution & tools | ✅ Passed | [`agent.py`](file:///d:/CareSatthi.AI/caresaathi/agent.py) |
| **FR-11** | Failure transparency & honest error returns | ✅ Passed | Throughout all workflows |
| **FR-12** | Synthetic demo fixtures | ✅ Passed | [`sample_plans.py`](file:///d:/CareSatthi.AI/synthetic_data/sample_plans.py) |

---

## 🎥 3-Minute Demo Video Script (Section 15)

* **0:00–0:20 — The Problem:** Explain the gap between receiving discharge papers and carrying out care at home.
* **0:20–0:50 — Plan Ingestion:** Load the synthetic Post-CABG recovery plan in the Web UI. Show extracted tasks, category pills, and exact quotation source snippets.
* **0:50–1:15 — Confirmation Gate:** Show the Confirmation Gate in proposed state. Review instructions and click *Confirm Plan* to activate the daily checklist.
* **1:15–1:35 — Daily Tracking:** Show today's tasks in time order. Mark Aspirin complete with a caregiver note.
* **1:35–2:00 — Ambiguity & Safety:** Load the ambiguous test plan. Show the system flagging missing doses and refusing to guess. Show emergency prompt with 112 alert and clinical boundary blocks on stopping medications.
* **2:00–2:30 — Clinician Report:** Generate the progress summary showing adherence rate, patient-reported symptoms, and unresolved questions.
* **2:30–3:00 — Fetch.ai Agent & Limitations:** Show the live Bech32 address (`agent1q039...`) and state prototype limitations honestly.

---

## 👥 Team Ownership & Roles
- **Utkarsh (Team Lead):** Architecture, integration, judging narrative, and presentation.
- **Ridhi (Product & Safety):** User journeys, care-plan workflows, deterministic safety rules, and acceptance testing.
- **Keshav (Domain Logic & Storage):** Python domain logic, Pydantic data models, SQLite ACID store, and report generation.
- **Aryan (Fetch.ai & Deployment):** Fetch.ai uAgents integration, Agentverse discovery preparation, README, and demo validation.

---

## ⚠️ Prototype Disclaimers & Limitations
- **Synthetic Data:** CareSaathi AI uses strictly fictional patients and synthetic care plans for this hackathon prototype.
- **Not a Medical Device:** It does not provide medical diagnoses, alter prescriptions, or replace healthcare professionals.
- **No Claimed Hospital Integration:** Progress reports are compiled locally for patient review; no external EHR transmission is claimed without verified hospital APIs.
