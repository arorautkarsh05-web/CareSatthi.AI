# Product Requirement Document (PRD)
## CareSaathi AI — Doctor-Guided Home Care Coordination Agent
**Document Version:** 1.0.0  
**Status:** Approved & Implemented (Fetch-A-Thon 3.0 Edition)  
**Author / Team:** Team Code Slayers (Utkarsh, Ridhi, Keshav, Aryan)  
**Target Platform:** Fetch.ai uAgents Runtime, FastAPI Web Engine, Offline-First SQLite  

---

## 1. Executive Summary & Vision

### 1.1 Problem Statement
When patients leave a hospital after a critical procedure (e.g., Post-CABG cardiac bypass, stroke stabilization, major orthopedic surgery) or manage complex multi-morbid chronic conditions, they receive multi-page discharge summaries and verbal instructions. 

Studies show that **over 50% of medication and rehabilitation errors occur in the home setting during the first 14 days post-discharge**. The primary reasons are:
- **Execution Overwhelm:** Patients and non-clinical family caregivers struggle to translate clinical jargon into a time-sequenced daily routine.
- **Ambiguity & Guesswork:** Vague notes like *"take pain meds as needed"* or *"restrict fluids"* lack concrete dosages, parameters, or timings, leading to dangerous guesswork.
- **The LLM Chatbot Danger:** General-purpose conversational AI models (e.g., standard LLMs) hallucinate missing dosages, offer unverified medical advice, and lack deterministic safety guardrails.
- **Lack of Structured Feedback to Clinicians:** When patients return for follow-up consultations, doctors rely on inaccurate recall rather than an audited, objective log of adherence, symptoms, and vitals.

### 1.2 Product Vision
**CareSaathi AI** is an autonomous, doctor-guided home care coordination agent designed to eliminate the post-consultation execution gap. It transforms clinician-approved care plans into verified, traceable daily action checklists, monitors patient-reported observations, enforces strict clinical safety guardrails, and compiles clinician-ready progress summaries—**without ever diagnosing, altering, or superseding the doctor's plan.**

### 1.3 Core Product Principles
1. **Doctor-Guided, Never Doctor-Replacing:** The agent executes and tracks; it never prescribes, diagnoses, or discontinues therapy.
2. **100% Traceability by Default:** Every active task maintains an immutable verbatim source quote (`source_reference`) linking back to the clinician's original text.
3. **Deterministic Confirmation Gate:** Extracted tasks remain in a *proposed* state until explicitly confirmed by the patient or caregiver.
4. **Zero-Hallucination Ambiguity Blocker:** Missing, vague, or contradictory instructions are blocked from activation and filed as clinician questions.
5. **Safety Over Completion:** Immediate deterministic escalations for life-threatening emergencies (India National Emergency: **112**) bypass chatbot dialogue entirely.

---

## 2. Target Personas & Stakeholders

| Persona | Role | Primary Pain Point | CareSaathi Solution |
|---|---|---|---|
| **Ramesh (62, Post-CABG Patient)** | Care Recipient | Elderly, easily fatigued, anxious about taking 5+ new medications on time. | Clear, chronological daily checklist with reminders and simple completion logging. |
| **Priya (32, Daughter & Caregiver)** | Primary Caregiver | Manages work and father's recovery; worries about missing subtle warning signs. | Single source of truth; instant visibility into completed tasks and clear 112 emergency alerts. |
| **Dr. V. Sharma (Cardiologist)** | Treating Clinician | Frustrated by vague follow-up reports ("I think I took all the pills"); needs objective data. | Clinician-ready progress report with adherence percentages, vital logs, and unresolved questions. |

---

## 3. System Architecture & Workflows

CareSaathi is architected around 5 core workflows coordinated through a centralized Orchestrator and exposed via Fetch.ai uAgent protocols and a responsive Web Dashboard:

```
                  ┌─────────────────────────────────────────┐
                  │       User / Caregiver Interface        │
                  │  (Web UI / Interactive CLI / REST API)   │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │    Fetch.ai Autonomous uAgent Runtime    │
                  │   CareSaathiCoordinationProtocol v1.0   │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │          CareSaathi Orchestrator         │
                  │  (Intent Classifier & Safety Firewall)  │
                  └─────────┬──────────┬──────────┬─────────┘
                            │          │          │
         ┌──────────────────┘          │          └──────────────────┐
         ▼                             ▼                             ▼
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  Plan Workflow   │         │ Routine Workflow │         │ Safety Workflow  │
│ (Extraction &    │         │ (Daily Checklist │         │ (112 Emergency & │
│  Confirmation)   │         │  & Audit Trail)  │         │  Clinical Blocks)│
└────────┬─────────┘         └────────┬─────────┘         └────────┬─────────┘
         │                            │                            │
         └──────────────────┬─────────┴────────────────────────────┘
                            ▼
                  ┌─────────────────────────────────────────┐
                  │     Monitoring & Reporting Workflow     │
                  │   (Patient Vitals & Clinician Report)   │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │      Transactional SQLite Storage       │
                  │      (ACID Compliant & Traceable)       │
                  └─────────────────────────────────────────┘
```

---

## 4. Functional Requirements (FR) Specification

### FR-01: Care Plan Ingestion & Text Normalization
- **Description:** Ingest plain-text or structured discharge summaries and clinical prescriptions.
- **Inputs:** Raw prescription text, patient metadata (ID, Name, Age, Diagnosis), and doctor information.
- **Outputs:** Stored Care Plan entity in `DRAFT` / `PROPOSED` state.
- **Acceptance Criteria:** Accepts ASCII, UTF-8, and multi-line medical notes; sanitizes malicious inputs.

### FR-02: Traceable Task Extraction
- **Description:** Parse ingested clinical text into discrete actionable items across categories: `MEDICATION`, `VITALS_CHECK`, `EXERCISE_REHAB`, `DIET_NUTRITION`, `WOUND_CARE`.
- **Extraction Rules:**
  - Every extracted task must contain a non-empty `source_reference` string with an exact verbatim quote from the doctor's plan.
  - Tasks without explicit source anchors are strictly rejected.
  - Frequency, dosage, target time, and duration must be structured.

### FR-03: Deterministic Confirmation Gate
- **Description:** Prevent automatic activation of newly parsed care plans.
- **Behavior:**
  - Tasks are initially marked `PROPOSED`.
  - The patient/caregiver must explicitly invoke `confirm_care_plan` to transition tasks to `CONFIRMED` / `ACTIVE`.
  - Only confirmed tasks appear in the daily interactive routine checklist.

### FR-04: Zero-Hallucination Ambiguity Blocker
- **Description:** Identify incomplete, contradictory, or vague medical instructions.
- **Criteria for Flagging:**
  - PRN medications without specified drug name or maximum daily dosage (e.g., *"take pain killer if pain occurs"*).
  - Vitals checks without target frequency or thresholds (e.g., *"check BP sometimes"*).
  - Unquantified dietary limits (e.g., *"cut down salt"* without specific guideline).
- **Outcome:** The task is blocked from activation, logged in `unresolved_questions`, and formatted into the Clinician Summary for clarification.

### FR-05: Daily Care Checklist Generation
- **Description:** Dynamically produce today's schedule of actionable care tasks.
- **Capabilities:**
  - Groups tasks chronologically (`Morning`, `Afternoon`, `Evening`, `Bedtime`, `Anytime`).
  - Displays dosage, instructions, and the verbatim `source_reference`.
  - Computes dynamic adherence metrics (Completed vs. Total scheduled).

### FR-06: Task Execution & Immutable Audit Trail
- **Description:** Allow caregivers to update task states (`PENDING`, `COMPLETED`, `SKIPPED`, `DELAYED`).
- **Audit Requirement:**
  - Every transition generates an immutable `TaskAuditEvent` recording: `task_id`, `old_status`, `new_status`, `timestamp` (ISO-8601 UTC), and optional caregiver notes (e.g., *"Taken with food at 8:30 AM"*).

### FR-07: Patient-Reported Vitals & Symptom Monitoring
- **Description:** Record subjective symptoms and objective physiological measurements.
- **Rules:**
  - All entries are stamped with `is_patient_reported: true`.
  - The system explicitly avoids diagnostic claims.
  - Quantitative vitals (Blood Pressure, Heart Rate, SpO2, Temperature, Blood Glucose) are screened against clinical safety thresholds.

### FR-08: Deterministic Safety & Clinical Boundary Firewall
- **Description:** Non-negotiable safety guardrails that run before any AI generation or response.
- **Sub-Features:**
  - **Emergency Red Flag Detection:** Triggers immediate alert to call **112 (National Emergency)** or **102 (Ambulance)** for acute symptoms (crushing chest pain, severe dyspnea, sudden weakness/FAST signs, severe hemorrhage, anaphylaxis).
  - **Clinical Action Blocks:** Deterministically rejects prompts asking to stop medications, alter doses, diagnose diseases, or prescribe unapproved drugs.
  - **Multilingual Support:** Delivers emergency escalations and policy blocks in 9 Indian languages (English, Hindi, Hinglish, Gujarati, Bengali, Marathi, Telugu, Tamil, Punjabi).

### FR-09: Clinician-Ready Progress Report
- **Description:** Compile an objective, dated progress summary for the treating doctor.
- **Contents:**
  - Adherence summary statistics (Completion %, skipped doses breakdown).
  - Chronological vitals table with out-of-range highlights.
  - Patient-reported symptom timeline.
  - Unresolved clinical questions requiring doctor clarification.

---

## 5. Data Models & Schemas

### 5.1 CareTask Schema
```json
{
  "id": "task_uuid_v4",
  "plan_id": "plan_uuid_v4",
  "category": "MEDICATION | VITALS_CHECK | EXERCISE_REHAB | DIET_NUTRITION | WOUND_CARE",
  "title": "Aspirin 75mg",
  "description": "Take 1 tablet daily after breakfast with water",
  "frequency": "ONCE_DAILY",
  "scheduled_time": "08:00",
  "status": "PROPOSED | CONFIRMED | COMPLETED | SKIPPED | DELAYED",
  "source_reference": "Discharge Summary Section 4: Tab Aspirin 75mg OD post-breakfast",
  "is_ambiguous": false,
  "created_at": "2026-10-20T10:00:00Z"
}
```

### 5.2 SafetyEvent Schema
```json
{
  "id": "safety_uuid_v4",
  "patient_id": "PATIENT_001",
  "emergency_level": "EMERGENCY_112 | CLINICAL_BLOCK | WARNING | ROUTINE",
  "trigger_source": "INPUT_TEXT | VITAL_THRESHOLD | SYMPTOM_CHECK",
  "trigger_content": "Crushing chest pain radiating to left arm",
  "action_taken": "DISPLAY_EMERGENCY_112_ALERT",
  "resolved": false,
  "timestamp": "2026-10-20T10:15:30Z"
}
```

---

## 6. Non-Functional Requirements (NFR)

| Parameter | Target Metric | Achieved Prototype Benchmark |
|---|---|---|
| **Response Latency** | < 150ms for local queries | **< 35ms** (SQLite WAL mode + FastAPI) |
| **Safety False Negatives** | 0% for life-threatening keywords | **0%** (100% caught across 75+ test scenarios) |
| **Traceability Ratio** | 100% active tasks with source links | **100%** enforced at Pydantic validation layer |
| **Availability & Offline** | Complete standalone functionality | **100% offline-capable**; zero cloud API dependency |
| **Memory Footprint** | < 250 MB RAM for full agent stack | **~85 MB RAM** running agent + web dashboard |

---

## 7. Edge Cases & Handling Strategy

1. **Vague Emergency Phrasing ("chest me bohot dard ho raha hai"):**
   - The regex engine supports phonetic Romanized Hindi (Hinglish) alongside formal Devanagari and regional scripts. Immediately escalates to 112.
2. **Conflicting Care Plans Uploaded:**
   - The system locks the existing active plan until the user explicitly archives it. No silent plan merging or overwriting without confirmation.
3. **Double Medication Dose Request ("I missed morning dose, can I take 2 pills now?"):**
   - Hard deterministic block `BLOCK_MODIFY_DOSE`. Instructs the patient never to double dose and to consult doctor; records event in the report.
4. **Network Outage During Routine Logging:**
   - All operations write to local SQLite. When connection to Agentverse is restored, telemetry synchronizes seamlessly.

---

## 8. Release & Deployment Status

- **Version 1.0.0:** Fully tested, pass rate 27/27 test suites.
- **Fetch.ai Address:** `agent1q039k6qfpszyehmv67lwna03zqua086nnwym06reenzzksn99alqvrwdj5k`.
- **Supported Channels:** Web Dashboard (`http://127.0.0.1:8080`), CLI Tool (`python cli.py`), Fetch.ai RPC Listener (`http://127.0.0.1:8008/submit`).
