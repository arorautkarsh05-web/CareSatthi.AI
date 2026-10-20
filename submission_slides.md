# CareSaathi AI — Fetch-A-Thon 3.0 Presentation Slides
**Doctor-Guided Home Care Coordination Agent**  
*GCET Edition | Version 1.0 | 20 October 2026*  
**Team Members:** Utkarsh (Lead), Ridhi (Product & Safety), Keshav (Domain Logic & Storage), Aryan (Fetch.ai & Deployment)

---

## Slide 1: Title & Value Proposition
* **Project Name:** CareSaathi AI
* **Subtitle:** Doctor-Guided Home Care Coordination Agent with Traceable Care-to-Action Architecture
* **One-Line Value Proposition:**  
  > *"CareSaathi turns a clinician-approved care plan into traceable daily actions, tracks patient-reported progress, and prepares a clinician-ready report — without altering the clinical plan."*
* **Core Philosophy:** Doctor-guided, not doctor-replacing. Execution over conversation. Safety over completion.

---

## Slide 2: The Problem
* **The Post-Consultation Execution Gap:**  
  After hospital discharge or chronic care consultations, patients and family caregivers struggle to translate complex medical prescriptions into daily routines at home.
* **Realistic Patient Scenario:**  
  A 62-year-old post-CABG patient leaves the hospital with 5 medications, wound care guidelines, spirometry routines, and dietary limits across multiple discharge sheets. Missed doses, forgotten vitals checks, and subjective uncertainties often lead to preventable complications or hospital readmissions.
* **Why Conversational LLMs Fail Here:**  
  Generic chatbots hallucinate missing doses, guess ambiguous instructions, and cannot provide verified audit trails or clinical boundary safeguards.

---

## Slide 3: The Solution — Care-to-Action Workflow
1. **Source-Linked Task Extraction:**  
   Parses doctor's text into structured daily tasks. Every task retains an immutable quote linking back to the exact doctor instruction.
2. **Deterministic Confirmation Gate:**  
   Extracted tasks remain in a *proposed* state until reviewed and confirmed by the patient/caregiver.
3. **Zero-Hallucination Ambiguity Blocker:**  
   Vague instructions (e.g. "take pain medicine as needed" without drug or dose) are deterministically blocked from activating and logged as *unresolved questions* for the doctor.
4. **Daily Interactive Checklist & Audit Trail:**  
   Tasks presented chronologically; updates (*completed, skipped, delayed*) recorded with ISO timestamps and caregiver notes.
5. **Patient-Reported Symptom & Vitals Log:**  
   Patient entries are explicitly tagged `patient-reported`—no automated clinical diagnoses inferred.
6. **Clinician-Ready Progress Report:**  
   Generates a dated, structured summary of adherence, vitals, symptoms, and unresolved questions for the treating doctor.

---

## Slide 4: Multi-Workflow Agent Architecture
```
User / Chat / Web UI
        │
        ▼
CareSaathi Fetch.ai uAgent (agent1q039k6qfpszyehmv67lwna03zqua086nnwym06reenzzksn99alqvrwdj5k)
        │
        ▼
CareSaathi Orchestrator (Intent Detection & Permission Checks)
        │
   ┌────┴──────────────────────────┬──────────────────────────┐
   ▼                               ▼                          ▼
Safety Workflow           Plan Workflow               Routine Workflow
(112 Emergencies &        (Task Extraction &          (Daily Checklist &
 Clinical Blocks)          Confirmation Gate)          Audit Event Trail)
   │                               │                          │
   └───────────────┬───────────────┴──────────────────────────┘
                   ▼
       Monitoring & Report Workflow
       (Patient-Reported Vitals & Clinician Summaries)
                   │
                   ▼
       SQLite Transactional Store (Traceable Records)
```

---

## Slide 5: Innovation, Safety & Clinical Guardrails
* **100% Traceability by Default:**  
  Every active task stores its original source snippet (`source_reference`), preventing detached or fabricated tasks.
* **Deterministic Emergency Escalation (India 112):**  
  Acute warning scenarios (crushing chest pain, severe dyspnea, stroke signs FAST, anaphylaxis, severe hemorrhage) bypass chatbot chit-chat and trigger immediate guidance to call **112**.
* **Hard Clinical Boundary Blocks:**  
  Deterministic rule engine strictly blocks prohibited queries (e.g., *"Can I stop Aspirin?"*, *"Can I double my dose?"*, *"Diagnose my illness"*).
* **Failure Transparency:**  
  The system never claims an action or doctor notification succeeded without verified confirmation.

---

## Slide 6: Technology Stack & Prototype Implementation
* **Agent Runtime:** Python + Fetch.ai `uagents` (v0.26.1).
* **Agent Protocol:** `CareSaathiCoordinationProtocol v1.0.0` with real tool actions (`set_care_plan`, `confirm_care_plan`, `get_daily_checklist`, `update_task_status`, `log_symptom`, `generate_progress_report`, `evaluate_safety`).
* **Validation & Storage:** Pydantic v2 schemas + SQLite transactional ACID database.
* **User Interfaces:**  
  1. Interactive CLI demo script (`python cli.py`) running all 8 journey steps in seconds.  
  2. Full-featured glassmorphism Web Application (`http://127.0.0.1:8080`) with live agent telemetry, safety alerts, and report viewer.
* **Agent Identity:** Bech32 address `agent1q039k6qfpszyehmv67lwna03zqua086nnwym06reenzzksn99alqvrwdj5k`.

---

## Slide 7: Measured Results, Honest Disclosures & Next Steps
* **Verified Prototype Test Results:**  
  * 100% of tasks in synthetic fixtures include traceable source snippets.  
  * 100% pass rate across all 9 integration tests and dedicated safety test suite.  
  * Ambiguity detector flagged 100% of test ambiguities with zero medication hallucinations.  
  * Average local checklist & report generation latency: < 50ms.
* **Honest Prototype Limitations:**  
  * Built using synthetic patient fixtures (not clinically validated on real patients).  
  * Ingestion operates on text/structured input (camera OCR out of MVP scope).  
  * Clinician messaging requires real hospital EHR integration before production deployment.
* **Future Roadmap:**  
  * Phase 2: Split specialist workflows into independently communicating Fetch.ai sub-agents.  
  * Phase 3: Integration with ABDM (Ayushman Bharat Digital Mission) for doctor care-plan syncing.
