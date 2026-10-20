/**
 * CareSaathi AI - Interactive Web Dashboard Client Logic
 * Handles real-time API communication, reactive UI updates,
 * confirmation gates, and deterministic safety alert triggers.
 */

// Global State
let currentPlanId = null;
let currentSyntheticPlans = {};
let pendingTaskAction = { taskId: null, status: null };

document.addEventListener("DOMContentLoaded", () => {
  initCapsuleAuth();
  initTabs();
  initAgentInfo();
  initSyntheticPresets();
  initPlanWorkflow();
  initChecklistWorkflow();
  initSymptomWorkflow();
  initSafetyWorkflow();
  initReportWorkflow();
  initChatWorkflow();
  initModals();

  // Load initial checklist and report
  fetchChecklist();
  fetchReport();
});

// Toast Notifications Helper
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = "toast";
  if (type === "error" || type === "emergency") {
    toast.style.borderLeftColor = "#ef4444";
  } else if (type === "warning") {
    toast.style.borderLeftColor = "#f59e0b";
  } else {
    toast.style.borderLeftColor = "#10b981";
  }
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching Logic
function initTabs() {
  const tabButtons = document.querySelectorAll(".nav-tab");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");

      // Auto-refresh when entering checklist or report tab
      if (targetId === "tab-checklist") fetchChecklist();
      if (targetId === "tab-report") fetchReport();
      if (targetId === "tab-symptoms") fetchSymptoms();
    });
  });
}

// Fetch.ai Agent Info
async function initAgentInfo() {
  try {
    const res = await fetch("/api/agent-info");
    const data = await res.json();
    if (data.address) {
      document.getElementById("agentAddressDisplay").textContent = data.address.substring(0, 16) + "...";
      document.getElementById("agentSpecAddress").textContent = data.address;
    }
  } catch (err) {
    console.error("Failed to load agent info:", err);
  }
}

// Synthetic Presets Loading
async function initSyntheticPresets() {
  try {
    const res = await fetch("/api/synthetic-plans");
    const data = await res.json();
    currentSyntheticPlans = data.plans || {};

    // Auto-populate with Post-CABG recovery plan on first load
    loadPreset("cardiac_recovery");

    document.getElementById("loadPresetCabg").addEventListener("click", () => loadPreset("cardiac_recovery"));
    document.getElementById("loadPresetDm").addEventListener("click", () => loadPreset("diabetes_hypertension"));
    document.getElementById("loadPresetAmbiguous").addEventListener("click", () => loadPreset("ambiguous_test_plan"));
  } catch (err) {
    console.error("Failed to load synthetic plans:", err);
  }
}

function loadPreset(key) {
  const plan = currentSyntheticPlans[key];
  if (!plan) return;
  document.getElementById("planPatientName").value = plan.patient_name;
  document.getElementById("planDoctorName").value = plan.doctor_name;
  document.getElementById("planDiagnosis").value = plan.diagnosis;
  document.getElementById("planSourceText").value = plan.text;
  showToast(`Loaded preset: ${plan.diagnosis}`);
}

// Plan Ingestion & Confirmation Gate (FR-01, FR-02, FR-03, FR-04)
function initPlanWorkflow() {
  const btnExtract = document.getElementById("btnExtractPlan");
  const btnConfirm = document.getElementById("btnConfirmPlan");

  btnExtract.addEventListener("click", async () => {
    const sourceText = document.getElementById("planSourceText").value.trim();
    if (!sourceText) {
      showToast("Please provide doctor's care plan text.", "warning");
      return;
    }

    btnExtract.disabled = true;
    btnExtract.textContent = "⏳ Parsing & Linking Sources...";

    try {
      const planId = `plan_${Date.now()}`;
      currentPlanId = planId;

      const payload = {
        plan_id: planId,
        patient_id: "Demo-Patient-01",
        patient_name: document.getElementById("planPatientName").value,
        doctor_name: document.getElementById("planDoctorName").value,
        diagnosis: document.getElementById("planDiagnosis").value,
        source_text: sourceText
      };

      const res = await fetch("/api/care-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      renderExtractedTasks(data.tasks);

      // Update Gate Status
      const gateBadge = document.getElementById("confirmationGateBadge");
      gateBadge.className = "badge-status badge-pending";
      gateBadge.textContent = "Gate: Proposed (Awaiting Confirmation)";

      btnConfirm.disabled = data.proposed_tasks === 0;

      // Summary chips
      document.getElementById("planExtractionSummary").style.display = "block";
      document.getElementById("summaryTotalTasks").textContent = `Total Tasks: ${data.total_tasks}`;
      document.getElementById("summaryProposedTasks").textContent = `Proposed: ${data.proposed_tasks}`;
      document.getElementById("summaryAmbiguousTasks").textContent = `Ambiguities: ${data.ambiguous_tasks}`;

      showToast(`Extracted ${data.total_tasks} tasks. Review against original source.`, "info");
    } catch (err) {
      showToast("Failed to extract care plan.", "error");
      console.error(err);
    } finally {
      btnExtract.disabled = false;
      btnExtract.innerHTML = "<span>⚡ Extract Structured Tasks & Trace Sources</span>";
    }
  });

  btnConfirm.addEventListener("click", async () => {
    if (!currentPlanId) return;

    btnConfirm.disabled = true;
    btnConfirm.textContent = "⏳ Confirming...";

    try {
      const res = await fetch("/api/care-plan/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: currentPlanId })
      });
      const data = await res.json();

      const gateBadge = document.getElementById("confirmationGateBadge");
      gateBadge.className = "badge-status badge-completed";
      gateBadge.textContent = "Gate: Confirmed & Active";

      showToast(data.message, "success");
      fetchChecklist();
      fetchReport();
    } catch (err) {
      showToast("Confirmation gate failed.", "error");
      console.error(err);
    } finally {
      btnConfirm.disabled = false;
      btnConfirm.innerHTML = "<span>✅ Tasks Confirmed & Activated</span>";
    }
  });
}

function renderExtractedTasks(tasks) {
  const container = document.getElementById("extractedTasksList");
  container.innerHTML = "";

  if (!tasks || tasks.length === 0) {
    container.innerHTML = `<p style="color: var(--text-dim); text-align: center; padding: 40px 0;">No tasks found.</p>`;
    return;
  }

  tasks.forEach(task => {
    const item = document.createElement("div");
    item.className = "task-item";

    const isAmb = task.is_ambiguous;
    const badgeHtml = isAmb
      ? `<span class="badge-status badge-delayed" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b;">Ambiguous (Requires Doctor Clarification)</span>`
      : `<span class="badge-status badge-pending">Proposed</span>`;

    const ambiguityBox = isAmb
      ? `<div class="task-ambiguity-alert">
           ⚠️ <strong>Clarification Required:</strong> ${task.ambiguity_reason}
           <br><span style="font-size: 11px;">CareSaathi does not invent missing doses or instructions. Flagged for next consult.</span>
         </div>`
      : "";

    item.innerHTML = `
      <div class="task-item-header">
        <span class="task-category-pill">${task.category}</span>
        <span class="task-time-badge">${task.scheduled_time_if_explicit || "As scheduled"}</span>
        ${badgeHtml}
      </div>
      <div class="task-instruction">${task.instruction_text}</div>
      <div class="task-source-snippet">
        <strong>Source reference:</strong> "${task.source_reference}"
      </div>
      ${ambiguityBox}
    `;
    container.appendChild(item);
  });
}

// Daily Checklist Workflow (FR-05, FR-06)
function initChecklistWorkflow() {
  document.getElementById("btnRefreshChecklist").addEventListener("click", fetchChecklist);
}

async function fetchChecklist() {
  try {
    const res = await fetch("/api/checklist");
    const data = await res.json();

    document.getElementById("statTotalTasks").textContent = data.total_tasks || 0;
    document.getElementById("statCompletedTasks").textContent = data.counts?.completed || 0;
    document.getElementById("statPendingTasks").textContent = data.counts?.pending || 0;

    const rate = data.total_tasks > 0
      ? Math.round((data.counts.completed / data.total_tasks) * 100)
      : 0;
    document.getElementById("statAdherenceRate").textContent = `${rate}%`;

    renderChecklist(data.checklist || []);
  } catch (err) {
    console.error("Failed to fetch checklist:", err);
  }
}

function renderChecklist(items) {
  const container = document.getElementById("dailyChecklistContainer");
  container.innerHTML = "";

  if (!items || items.length === 0) {
    container.innerHTML = `
      <p style="color: var(--text-dim); text-align: center; padding: 40px 0;">
        No active tasks found. Please ingest and confirm a care plan in Step 1.
      </p>
    `;
    return;
  }

  items.forEach(task => {
    const card = document.createElement("div");
    card.className = "task-item";

    let statusBadgeClass = "badge-pending";
    if (task.status === "completed") statusBadgeClass = "badge-completed";
    else if (task.status === "skipped") statusBadgeClass = "badge-skipped";
    else if (task.status === "delayed") statusBadgeClass = "badge-delayed";

    card.innerHTML = `
      <div class="task-item-header">
        <span class="task-category-pill">${task.category}</span>
        <span class="task-time-badge">${task.scheduled_time}</span>
        <span class="badge-status ${statusBadgeClass}">${task.status.toUpperCase()}</span>
      </div>
      <div class="task-instruction">${task.instruction_text}</div>
      <div class="task-source-snippet">
        <strong>Source snippet:</strong> "${task.source_reference}"
      </div>
      <div class="task-actions">
        <button class="btn btn-secondary btn-sm" onclick="openTaskModal('${task.task_id}', 'completed', '${escapeHtml(task.instruction_text)}')">
          ✅ Mark Complete
        </button>
        <button class="btn btn-secondary btn-sm" onclick="openTaskModal('${task.task_id}', 'delayed', '${escapeHtml(task.instruction_text)}')">
          ⏳ Delay
        </button>
        <button class="btn btn-secondary btn-sm" onclick="openTaskModal('${task.task_id}', 'skipped', '${escapeHtml(task.instruction_text)}')">
          ⏭️ Skip
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

function escapeHtml(text) {
  return (text || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

// Modal handling for Task Updates with Notes
function openTaskModal(taskId, status, instruction) {
  pendingTaskAction = { taskId, status };
  document.getElementById("modalTaskTitle").textContent = `Mark as ${status.toUpperCase()}`;
  document.getElementById("modalTaskInstruction").textContent = instruction;
  document.getElementById("modalTaskNote").value = "";
  document.getElementById("taskNoteModal").classList.add("active");
}

function initModals() {
  document.getElementById("btnCancelTaskUpdate").addEventListener("click", () => {
    document.getElementById("taskNoteModal").classList.remove("active");
  });

  document.getElementById("btnConfirmTaskUpdate").addEventListener("click", async () => {
    const note = document.getElementById("modalTaskNote").value.trim();
    const { taskId, status } = pendingTaskAction;
    if (!taskId) return;

    try {
      const res = await fetch("/api/task/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: taskId,
          status: status,
          note: note || undefined
        })
      });
      const data = await res.json();
      showToast(data.message, "success");
      document.getElementById("taskNoteModal").classList.remove("active");
      fetchChecklist();
      fetchReport();
    } catch (err) {
      showToast("Failed to update task.", "error");
      console.error(err);
    }
  });

  document.getElementById("btnCloseEmergencyModal").addEventListener("click", () => {
    document.getElementById("emergencyModal").classList.remove("active");
  });
}

// Symptom & Vitals Logging (FR-07, FR-08)
function initSymptomWorkflow() {
  const btnLog = document.getElementById("btnLogSymptom");

  document.querySelectorAll(".quick-sym-tag").forEach(tag => {
    tag.addEventListener("click", () => {
      document.getElementById("symptomDesc").value = tag.getAttribute("data-text");
      const r = tag.getAttribute("data-reading");
      const t = tag.getAttribute("data-type");
      if (r) document.getElementById("symptomReading").value = r;
      if (t) document.getElementById("symptomReadingType").value = t;
    });
  });

  btnLog.addEventListener("click", async () => {
    const desc = document.getElementById("symptomDesc").value.trim();
    if (!desc) {
      showToast("Please enter a symptom description.", "warning");
      return;
    }

    const readingVal = document.getElementById("symptomReading").value;
    const readingType = document.getElementById("symptomReadingType").value;

    const payload = {
      patient_id: "Demo-Patient-01",
      description: desc,
      reading: readingVal ? parseFloat(readingVal) : null,
      unit: readingType === "blood_pressure" ? "mmHg" : (readingType === "blood_glucose" ? "mg/dL" : null),
      reading_type: readingType || null
    };

    try {
      const res = await fetch("/api/symptom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      // Check if deterministic safety triggered an emergency
      if (data.requires_emergency_action) {
        triggerEmergencyAlert(data.safety_message || "Acute distress detected. Call 112 immediately.");
      } else {
        showToast(data.message, "success");
      }

      document.getElementById("symptomDesc").value = "";
      document.getElementById("symptomReading").value = "";
      fetchSymptoms();
      fetchReport();
    } catch (err) {
      showToast("Failed to log symptom.", "error");
      console.error(err);
    }
  });
}

async function fetchSymptoms() {
  try {
    const res = await fetch("/api/symptoms");
    const data = await res.json();
    const container = document.getElementById("symptomHistoryList");
    container.innerHTML = "";

    if (!data || data.length === 0) {
      container.innerHTML = `<p style="color: var(--text-dim); text-align: center; padding: 40px 0;">No symptoms recorded.</p>`;
      return;
    }

    data.forEach(s => {
      const card = document.createElement("div");
      card.className = "task-item";
      card.innerHTML = `
        <div class="task-item-header">
          <span class="task-time-badge">${s.reported_at ? s.reported_at.substring(11, 16) : ""}</span>
          <span class="badge-status badge-completed">${s.source_label}</span>
          ${s.emergency_level !== "normal" ? `<span class="badge-status badge-delayed">${s.emergency_level.toUpperCase()}</span>` : ""}
        </div>
        <div class="task-instruction">${s.description}</div>
        ${s.reading ? `<div style="font-size: 13px; color: #38bdf8;">Reported Reading: <strong>${s.reading}</strong></div>` : ""}
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Failed to fetch symptoms:", err);
  }
}

// Deterministic Safety Sandbox (FR-08)
function initSafetyWorkflow() {
  document.querySelectorAll(".safety-test-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const text = chip.getAttribute("data-text");
      document.getElementById("customSafetyQuery").value = text;
      runSafetyCheck(text);
    });
  });

  document.getElementById("btnTestSafety").addEventListener("click", () => {
    const text = document.getElementById("customSafetyQuery").value.trim();
    if (text) runSafetyCheck(text);
  });

  fetchSafetyEvents();
}

async function runSafetyCheck(text) {
  try {
    const res = await fetch("/api/safety-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    renderSafetyResult(data);
    fetchSafetyEvents();

    if (data.emergency_level === "emergency") {
      triggerEmergencyAlert(data.message);
    }
  } catch (err) {
    console.error("Safety evaluation failed:", err);
  }
}

function renderSafetyResult(res) {
  const container = document.getElementById("safetyResultContainer");
  const badge = document.getElementById("safetyLevelBadge");

  if (res.emergency_level === "emergency") {
    badge.className = "badge-status badge-emergency";
    badge.textContent = "CRITICAL EMERGENCY (112)";
    container.innerHTML = `
      <div style="color: #ef4444; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
        🚨 LIFE-THREATENING EMERGENCY TRIGGERED
      </div>
      <div style="font-size: 14px; line-height: 1.6; color: #fca5a5; margin-bottom: 12px;">
        ${res.message}
      </div>
      <div style="font-size: 12px; color: #94a3b8; font-family: monospace;">
        Scenario Code: <strong>${res.scenario_code}</strong> | Rule Version: 1.0.0
      </div>
    `;
  } else if (res.emergency_level === "clinical_block") {
    badge.className = "badge-status badge-delayed";
    badge.textContent = "CLINICAL ACTION BLOCKED";
    container.innerHTML = `
      <div style="color: #f59e0b; font-size: 16px; font-weight: 700; margin-bottom: 8px;">
        🛑 PROHIBITED CLINICAL ACTION BLOCKED
      </div>
      <div style="font-size: 14px; line-height: 1.6; color: #fde68a; margin-bottom: 12px;">
        ${res.message}
      </div>
      <div style="font-size: 12px; color: #94a3b8; font-family: monospace;">
        Scenario Code: <strong>${res.scenario_code}</strong> | Guardrail: Doctor-Guided Home Care
      </div>
    `;
  } else {
    badge.className = "badge-status badge-completed";
    badge.textContent = "PASSED (NORMAL)";
    container.innerHTML = `
      <div style="color: #10b981; font-size: 15px; font-weight: 600; margin-bottom: 8px;">
        ✅ Safe Observation
      </div>
      <div style="font-size: 14px; color: #d1fae5;">
        ${res.message}
      </div>
    `;
  }
}

async function fetchSafetyEvents() {
  try {
    const res = await fetch("/api/safety-events");
    const events = await res.json();
    const container = document.getElementById("recentSafetyEventsList");
    container.innerHTML = "";

    if (!events || events.length === 0) {
      container.innerHTML = `<span style="color: var(--text-dim);">No safety incidents logged.</span>`;
      return;
    }

    events.slice(0, 5).forEach(e => {
      const item = document.createElement("div");
      item.style.padding = "6px 0";
      item.style.borderBottom = "1px solid rgba(255,255,255,0.06)";
      item.innerHTML = `
        <span style="color: #94a3b8;">${e.triggered_at ? e.triggered_at.substring(11, 16) : ""}</span> - 
        <strong style="color: ${e.emergency_level === 'emergency' ? '#ef4444' : '#f59e0b'};">${e.scenario_code}</strong>: 
        <span>${e.action_taken}</span>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.error("Failed to load safety events:", err);
  }
}

function triggerEmergencyAlert(text) {
  document.getElementById("emergencyModalText").textContent = text;
  document.getElementById("emergencyModal").classList.add("active");
}

// Doctor Progress Report (FR-09)
function initReportWorkflow() {
  document.getElementById("btnRefreshReport").addEventListener("click", fetchReport);
  document.getElementById("btnPrintReport").addEventListener("click", () => {
    window.print();
  });
}

async function fetchReport() {
  try {
    const res = await fetch("/api/report");
    const data = await res.json();
    const container = document.getElementById("reportContentContainer");

    // Convert markdown to clean HTML view
    container.innerHTML = renderMarkdownToHtml(data.report_markdown || "");
  } catch (err) {
    console.error("Failed to fetch report:", err);
  }
}

function renderMarkdownToHtml(md) {
  if (!md) return "<p>No report data.</p>";

  // Simple, clean Markdown renderer for headings, tables, quotes, lists
  let html = md
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^#### (.*$)/gim, '<h4 style="color:#94a3b8; margin: 12px 0 6px;">$1</h4>')
    .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/`([^`]+)`/gim, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">$1</code>');

  // Convert Markdown tables
  const lines = html.split("\n");
  let inTable = false;
  let tableHtml = "";
  const outputLines = [];

  for (let line of lines) {
    line = line.trim();
    if (line.startsWith("|") && line.endsWith("|")) {
      if (!inTable) {
        inTable = true;
        tableHtml = "<table><tbody>";
      }
      if (line.includes("---")) {
        // Separator line
        continue;
      }
      const cells = line.split("|").filter((c, i, a) => i > 0 && i < a.length - 1);
      tableHtml += "<tr>" + cells.map(c => `<td>${c.trim()}</td>`).join("") + "</tr>";
    } else {
      if (inTable) {
        tableHtml += "</tbody></table>";
        outputLines.push(tableHtml);
        inTable = false;
      }
      outputLines.push(line ? `<p style="margin: 4px 0;">${line}</p>` : "<br>");
    }
  }

  if (inTable) {
    tableHtml += "</tbody></table>";
    outputLines.push(tableHtml);
  }

  return outputLines.join("\n");
}

// Chat Workflow with Multilingual Support (English, Hindi, Hinglish, Gujarati, Bengali, Marathi, Telugu, Tamil, Punjabi)
let currentChatLanguage = "en";

const MULTILINGUAL_CHAT_CONFIG = {
  en: {
    name: "English",
    placeholder: "Ask for today's checklist, log a symptom, or paste care instructions...",
    greeting: "Hello! I am your doctor-guided home care coordinator. You can ask for today's checklist, log a symptom, or request a progress report.",
    prompts: [
      "Show today's checklist",
      "Generate progress report",
      "Mild headache after morning walk",
      "Can I stop taking Aspirin?"
    ]
  },
  hi: {
    name: "हिन्दी (Hindi)",
    placeholder: "आज की चेकलिस्ट पूछें, लक्षण दर्ज करें या सवाल पूछें...",
    greeting: "नमस्ते! मैं आपका डॉक्टर-निर्देशित केयरसाथी AI हूँ। आप आज की दवाइयों की चेकलिस्ट देख सकते हैं, लक्षण दर्ज कर सकते हैं या डॉक्टर रिपोर्ट बनवा सकते हैं।",
    prompts: [
      "आज की चेकलिस्ट दिखाओ",
      "डॉक्टर रिपोर्ट बनाओ",
      "हल्का सिरदर्द और कमजोरी महसूस हो रही है",
      "क्या मैं दवा बंद कर दूं?"
    ]
  },
  hinglish: {
    name: "Hinglish",
    placeholder: "Aaj ka checklist pucho, symptom log karo, ya query pucho...",
    greeting: "Namaste! Main aapka CareSaathi AI home care coordinator hoon. Aap aaj ki routine check kar sakte hain, symptoms log kar sakte hain, ya doctor report bana sakte hain.",
    prompts: [
      "Aaj ka checklist dikhao",
      "Doctor progress report generate karo",
      "Thoda sir dard aur thakan lag rahi hai",
      "Kya main aspirin band kar du?"
    ]
  },
  gu: {
    name: "ગુજરાતી (Gujarati)",
    placeholder: "આજનો ચેકલિસ્ટ પૂછો, લક્ષણો નોંધો...",
    greeting: "નમસ્તે! હું તમારો CareSaathi AI કેર કોઓર્ડિનેટર છું. તમે આજની દવાઓની યાદી જોઈ શકો છો અથવા રિપોર્ટ બનાવી શકો છો.",
    prompts: [
      "આજનો ચેકલિસ્ટ બતાવો",
      "ડૉક્ટર રિપોર્ટ બનાવો",
      "સવારે ચાલ્યા પછી થોડું માથું દુખે છે",
      "શું હું દવા બંધ કરી શકું?"
    ]
  },
  bn: {
    name: "বাংলা (Bengali)",
    placeholder: "আজকের চেকলিস্ট জিজ্ঞাসা করুন, উপসর্গ রেকর্ড করুন...",
    greeting: "নমস্কার! আমি আপনার CareSaathi AI কেয়ার কোঅর্ডিনেটর। আপনি আজকের ওষুধের রুটিন দেখতে পারেন বা ডাক্তারের রিপোর্ট তৈরি করতে পারেন।",
    prompts: [
      "আজকের চেকলিস্ট দেখাও",
      "ডাক্তারের রিপোর্ট তৈরি করুন",
      "সামান্য মাথা ব্যথা করছে",
      "আমি কি ওষুধ বন্ধ করতে পারি?"
    ]
  },
  mr: {
    name: "मराठी (Marathi)",
    placeholder: "आजची चेकलिस्ट विचारा, लक्षणे नोंदवा...",
    greeting: "नमस्कार! मी तुमचा CareSaathi AI केअर कोऑर्डिनेटर आहे. आपण आजची औषधांची दिनचर्या पाहू शकता किंवा अहवाल तयार करू शकता.",
    prompts: [
      "आजची चेकलिस्ट दाखवा",
      "अहवाल तयार करा",
      "सकाळी डोकेदुखी जाणवत आहे",
      "मी औषध बंद करू का?"
    ]
  },
  te: {
    name: "తెలుగు (Telugu)",
    placeholder: "నేటి చెక్‌లిస్ట్ అడగండి, లక్షణాలను నమోదు చేయండి...",
    greeting: "నమస్కారం! నేను మీ CareSaathi AI సంరక్షణ సమన్వయకర్తను. మీరు నేటి మందుల వివరాలు చూడవచ్చు లేదా నివేదికను రూపొందించవచ్చు.",
    prompts: [
      "నేటి చెక్‌లిస్ట్ చూపించు",
      "వైద్యుడి నివేదిక పొందండి",
      "కొద్దిగా తలనెప్పిగా ఉంది"
    ]
  },
  ta: {
    name: "தமிழ் (Tamil)",
    placeholder: "இன்றைய பட்டியலைக் கேளுங்கள், அறிகுறிகளைப் பதிவு செய்யுங்கள்...",
    greeting: "வணக்கம்! நான் உங்கள் CareSaathi AI பராமரிப்பு ஒருங்கிணைப்பாளர். இன்றைய மருந்துகளைப் பார்க்கலாம் அல்லது அறிக்கை உருவாக்கலாம்.",
    prompts: [
      "இன்றைய பட்டியல் காட்டு",
      "அறிக்கை உருவாக்கு",
      "லேசான தலைவலி உள்ளது"
    ]
  },
  pa: {
    name: "ਪੰਜਾਬੀ (Punjabi)",
    placeholder: "ਅੱਜ ਦੀ ਚੈੱਕਲਿਸਟ ਪੁੱਛੋ, ਲੱਛਣ ਦਰਜ ਕਰੋ...",
    greeting: "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ CareSaathi AI ਕੇਅਰ ਕੋਆਰਡੀਨੇਟਰ ਹਾਂ। ਤੁਸੀਂ ਅੱਜ ਦੀਆਂ ਦਵਾਈਆਂ ਦੀ ਸੂਚੀ ਦੇਖ ਸਕਦੇ ਹੋ।",
    prompts: [
      "ਅੱਜ ਦੀ ਚੈੱਕਲਿਸਟ ਦਿਖਾਓ",
      "ਰਿਪੋਰਟ ਬਣਾਓ",
      "ਸਿਰ ਦਰਦ ਹੋ ਰਿਹਾ ਹੈ"
    ]
  }
};

function initChatWorkflow() {
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const messages = document.getElementById("chatMessages");
  const langSelect = document.getElementById("chatLanguageSelect");
  const langBadge = document.getElementById("chatCurrentLangBadge");
  const promptContainer = document.getElementById("chatQuickPrompts");
  const initialGreeting = document.getElementById("chatInitialGreeting");

  // Render prompts on load
  updateChatLanguageUI("en");

  if (langSelect) {
    langSelect.addEventListener("change", (e) => {
      const selectedLang = e.target.value;
      currentChatLanguage = selectedLang;
      updateChatLanguageUI(selectedLang);
      showToast(`Chat language set to ${MULTILINGUAL_CHAT_CONFIG[selectedLang]?.name || selectedLang}`, "info");
    });
  }

  function updateChatLanguageUI(lang) {
    const config = MULTILINGUAL_CHAT_CONFIG[lang] || MULTILINGUAL_CHAT_CONFIG["en"];
    if (langBadge) langBadge.textContent = `Current: ${config.name}`;
    if (input) input.placeholder = config.placeholder;
    if (initialGreeting) {
      initialGreeting.innerHTML = `<strong>CareSaathi AI (${config.name}):</strong> ${config.greeting}`;
    }

    // Populate quick suggestion prompt chips
    if (promptContainer) {
      promptContainer.innerHTML = "";
      config.prompts.forEach(pText => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "preset-chip";
        chip.style.fontSize = "12px";
        chip.style.padding = "4px 12px";
        chip.textContent = pText;
        chip.addEventListener("click", () => {
          input.value = pText;
          form.dispatchEvent(new Event("submit", { cancelable: true }));
        });
        promptContainer.appendChild(chip);
      });
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    // Append User Message
    const userDiv = document.createElement("div");
    userDiv.style.alignSelf = "flex-end";
    userDiv.style.background = "rgba(6, 182, 212, 0.2)";
    userDiv.style.border = "1px solid rgba(6, 182, 212, 0.4)";
    userDiv.style.padding = "10px 14px";
    userDiv.style.borderRadius = "12px 12px 2px 12px";
    userDiv.style.fontSize = "14px";
    userDiv.style.maxWidth = "80%";
    userDiv.innerHTML = `<strong>You:</strong> ${escapeHtml(text)}`;
    messages.appendChild(userDiv);

    input.value = "";
    messages.scrollTop = messages.scrollHeight;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          language: currentChatLanguage
        })
      });
      const data = await res.json();

      const agentDiv = document.createElement("div");
      agentDiv.style.alignSelf = "flex-start";
      agentDiv.style.background = "rgba(16, 185, 129, 0.15)";
      agentDiv.style.border = "1px solid rgba(16, 185, 129, 0.3)";
      agentDiv.style.padding = "10px 14px";
      agentDiv.style.borderRadius = "12px 12px 12px 2px";
      agentDiv.style.fontSize = "14px";
      agentDiv.style.maxWidth = "80%";

      if (data.emergency_level === "emergency") {
        agentDiv.style.background = "rgba(239, 68, 68, 0.2)";
        agentDiv.style.borderColor = "rgba(239, 68, 68, 0.5)";
        agentDiv.innerHTML = `<strong>🚨 CareSaathi Safety Alert:</strong> ${data.message}`;
        triggerEmergencyAlert(data.message);
      } else if (data.status === "blocked") {
        agentDiv.style.background = "rgba(245, 158, 11, 0.18)";
        agentDiv.style.borderColor = "rgba(245, 158, 11, 0.4)";
        agentDiv.innerHTML = `<strong>🛑 Clinical Boundary:</strong> ${data.message}`;
      } else {
        const langLabel = MULTILINGUAL_CHAT_CONFIG[data.language || currentChatLanguage]?.name || "CareSaathi AI";
        agentDiv.innerHTML = `<strong>CareSaathi AI (${langLabel}):</strong><br>${data.message.replace(/\n/g, '<br>')}`;
      }

      messages.appendChild(agentDiv);
      messages.scrollTop = messages.scrollHeight;
    } catch (err) {
      console.error("Chat error:", err);
    }
  });
}

// ==========================================================================
// Capsule Login Authentication & Security Timeout (2 Invalid -> 10s Cooldown)
// ==========================================================================

let failedAuthAttempts = 0;
let isCooldownActive = false;
let cooldownInterval = null;

function initCapsuleAuth() {
  const modal = document.getElementById("loginCapsuleModal");
  const form = document.getElementById("capsuleLoginForm");
  const nameInput = document.getElementById("loginName");
  const emailInput = document.getElementById("loginEmail");
  const mobileInput = document.getElementById("loginMobile");
  const submitBtn = document.getElementById("btnLoginSubmit");
  const card = document.getElementById("capsuleCard");
  const timeoutBanner = document.getElementById("capsuleTimeoutBanner");
  const cooldownTimerSpan = document.getElementById("cooldownTimer");
  const attemptsCountSpan = document.getElementById("attemptsCount");
  const mainWrapper = document.getElementById("mainAppWrapper");
  const userBadge = document.getElementById("userSessionBadge");
  const userNameSpan = document.getElementById("userSessionName");
  const logoutBtn = document.getElementById("btnLogoutSession");

  // Check if session is already authenticated
  const savedUser = sessionStorage.getItem("caresaathi_authenticated_user");
  if (savedUser) {
    try {
      const userObj = JSON.parse(savedUser);
      unlockDashboard(userObj);
    } catch (e) {
      sessionStorage.removeItem("caresaathi_authenticated_user");
    }
  }

  // Real-time mobile input digits filter (only allow digits, max 10)
  mobileInput.addEventListener("input", (e) => {
    e.target.value = e.target.value.replace(/\D/g, "").slice(0, 10);
    clearFieldError("mobile");
  });

  nameInput.addEventListener("input", () => clearFieldError("name"));
  emailInput.addEventListener("input", () => clearFieldError("email"));

  // Form Submit Handler
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (isCooldownActive) return;

    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const mobile = mobileInput.value.trim();

    // Validation
    let isValid = true;

    // 1. Name validation (min 2 characters, valid letters/spaces)
    if (!name || name.length < 2 || !/^[a-zA-Z\s.]{2,50}$/.test(name)) {
      setFieldError("name", "⚠️ Please enter a valid name (at least 2 letters, alphabetic).");
      isValid = false;
    } else {
      clearFieldError("name");
    }

    // 2. Email validation (RFC 5322 standard email regex)
    const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!email || !emailRegex.test(email)) {
      setFieldError("email", "⚠️ Enter a valid email address (e.g. name@domain.com).");
      isValid = false;
    } else {
      clearFieldError("email");
    }

    // 3. Mobile validation (10 digits starting with 6, 7, 8, or 9)
    const mobileRegex = /^[6-9]\d{9}$/;
    if (!mobile || !mobileRegex.test(mobile)) {
      setFieldError("mobile", "⚠️ Enter a valid 10-digit mobile number starting with 6, 7, 8, or 9.");
      isValid = false;
    } else {
      clearFieldError("mobile");
    }

    // If validation fails
    if (!isValid) {
      failedAuthAttempts++;
      attemptsCountSpan.textContent = failedAuthAttempts;
      card.classList.remove("shake");
      void card.offsetWidth; // Trigger reflow to restart CSS shake animation
      card.classList.add("shake");

      showToast(`Invalid credentials! Failed attempt ${failedAuthAttempts}/2`, "error");

      // Check if 2 failed attempts reached -> trigger 10-second security cooldown
      if (failedAuthAttempts >= 2) {
        startSecurityCooldown();
      }
      return;
    }

    // Validation Succeeded!
    failedAuthAttempts = 0;
    attemptsCountSpan.textContent = "0";

    const userObj = {
      name,
      email,
      mobile: "+91 " + mobile,
      loginTime: new Date().toISOString()
    };
    sessionStorage.setItem("caresaathi_authenticated_user", JSON.stringify(userObj));

    // Success animation on capsule card
    card.classList.add("success-exit");
    showToast(`Verification successful! Welcome, ${name}.`, "success");

    setTimeout(() => {
      unlockDashboard(userObj);
      card.classList.remove("success-exit");
    }, 380);
  });

  // Logout / Switch User handler
  logoutBtn.addEventListener("click", () => {
    sessionStorage.removeItem("caresaathi_authenticated_user");
    mainWrapper.classList.add("main-app-locked");
    userBadge.style.display = "none";
    modal.classList.add("active");
    nameInput.value = "";
    emailInput.value = "";
    mobileInput.value = "";
    clearFieldError("name");
    clearFieldError("email");
    clearFieldError("mobile");
    failedAuthAttempts = 0;
    attemptsCountSpan.textContent = "0";
    showToast("Session closed. Authenticate to access dashboard.", "info");
  });

  function unlockDashboard(userObj) {
    modal.classList.remove("active");
    mainWrapper.classList.remove("main-app-locked");
    userBadge.style.display = "flex";
    userNameSpan.textContent = userObj.name;

    // Update patient name across UI forms
    const planPatientNameInput = document.getElementById("planPatientName");
    if (planPatientNameInput) {
      planPatientNameInput.value = `${userObj.name} (Verified)`;
    }
  }

  function setFieldError(field, msg) {
    const wrap = document.getElementById(`wrap${capitalize(field)}`);
    const err = document.getElementById(`${field}Error`);
    if (wrap) wrap.classList.add("has-error");
    if (err) err.textContent = msg;
  }

  function clearFieldError(field) {
    const wrap = document.getElementById(`wrap${capitalize(field)}`);
    const err = document.getElementById(`${field}Error`);
    if (wrap) wrap.classList.remove("has-error");
    if (err) err.textContent = "";
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function startSecurityCooldown() {
    isCooldownActive = true;
    let secondsLeft = 10;
    timeoutBanner.style.display = "flex";
    cooldownTimerSpan.textContent = secondsLeft;

    // Disable inputs and button
    nameInput.disabled = true;
    emailInput.disabled = true;
    mobileInput.disabled = true;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>⏳ Security Timeout (${secondsLeft}s)...</span>`;

    showToast("⚠️ 2 invalid attempts detected! 10-second security timeout started.", "warning");

    clearInterval(cooldownInterval);
    cooldownInterval = setInterval(() => {
      secondsLeft--;
      cooldownTimerSpan.textContent = secondsLeft;
      submitBtn.innerHTML = `<span>⏳ Security Timeout (${secondsLeft}s)...</span>`;

      if (secondsLeft <= 0) {
        clearInterval(cooldownInterval);
        isCooldownActive = false;
        failedAuthAttempts = 0;
        attemptsCountSpan.textContent = "0";
        timeoutBanner.style.display = "none";

        // Re-enable inputs
        nameInput.disabled = false;
        emailInput.disabled = false;
        mobileInput.disabled = false;
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Verify & Unlock Care Dashboard →</span>`;

        clearFieldError("name");
        clearFieldError("email");
        clearFieldError("mobile");
        showToast("Timeout expired. You may now enter your details.", "info");
      }
    }, 1000);
  }
}
