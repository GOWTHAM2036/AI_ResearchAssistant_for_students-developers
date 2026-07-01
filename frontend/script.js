/* Frontend controller for pipeline streaming + history browsing */

let isRunning = false;
let timerInterval = null;
let startTime = null;
let briefingHtml = "";
let historyEntries = [];
let selectedHistoryId = null;
const LOGIN_URL = "/login";

const AGENT_COLORS = {
  Manager: "#7c3aed",
  Researcher: "#2563eb",
  Analyst: "#059669",
  Writer: "#d97706",
  Delivery: "#dc2626",
  System: "#64748b",
};

async function verifySessionOrRedirect() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    window.location.href = LOGIN_URL;
    return false;
  }

  try {
    const response = await fetch("/api/protected", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_name");
      localStorage.removeItem("user_email");
      window.location.href = LOGIN_URL;
      return false;
    }
  } catch (error) {
    // If backend is temporarily unavailable, keep the user on the page.
  }

  return true;
}

async function doLogout() {
  const token = localStorage.getItem("access_token");
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
  } catch (error) {
    // Keep client-side logout reliable even if server logout call fails.
  }

  localStorage.removeItem("access_token");
  localStorage.removeItem("user_name");
  localStorage.removeItem("user_email");
  window.location.href = LOGIN_URL;
}

window.doLogout = doLogout;

function startPipeline() {
  const topicInput = document.getElementById("topicInput");
  const emailInput = document.getElementById("emailInput");
  const topic = topicInput.value.trim();
  const email = emailInput.value.trim();

  if (!topic || topic.length > 150) {
    topicInput.focus();
    topicInput.style.borderColor = "#dc2626";
    setTimeout(() => (topicInput.style.borderColor = ""), 1500);
    showToast('Please enter a short research topic (< 150 chars, e.g. "NVIDIA AI chips 2026")');
    return;
  }

  if (isRunning) return;
  isRunning = true;

  const btn = document.getElementById("deployBtn");
  btn.disabled = true;
  btn.classList.add("loading");
  btn.querySelector(".btn-deploy__text").textContent = "Agents Working...";

  const badge = document.getElementById("statusBadge");
  badge.className = "header__badge running";
  badge.querySelector("span:last-child").textContent = "Running";

  resetAgentCards();
  document.getElementById("activityPanel").style.display = "block";
  document.getElementById("activityFeed").innerHTML = "";
  document.getElementById("briefingPanel").style.display = "none";

  startTime = Date.now();
  timerInterval = setInterval(updateTimer, 100);

  streamPipeline(topic, email);
}

async function streamPipeline(topic, email) {
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, email }),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          handleEvent(event);
        } catch (e) {
          // Ignore malformed events.
        }
      }
    }

    if (buffer.startsWith("data: ")) {
      try {
        const event = JSON.parse(buffer.slice(6));
        handleEvent(event);
      } catch (e) {
        // Ignore malformed trailing event.
      }
    }
  } catch (err) {
    addLogEntry("System", `Connection error: ${err.message}`, "#dc2626");
    const badge = document.getElementById("statusBadge");
    badge.className = "header__badge error";
    badge.querySelector("span:last-child").textContent = "Error";
    showToast(`Error: ${err.message}`);
  } finally {
    finishPipeline();
  }
}

function handleEvent(event) {
  const type = event.type;

  switch (type) {
    case "log":
      addLogEntry(event.agent, event.message, AGENT_COLORS[event.agent] || "#64748b");
      break;

    case "status":
      updateAgentStatus(event.agent, event.status);
      break;

    case "result":
      if (event.data) {
        const summary = Object.entries(event.data)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" • ");
        addLogEntry(event.agent, `Result -> ${summary}`, AGENT_COLORS[event.agent] || "#64748b");
      }
      break;

    case "pipeline":
      if (event.status === "complete") {
        handlePipelineComplete(event);
      } else if (event.status === "error") {
        addLogEntry("System", `Pipeline error: ${event.message}`, "#dc2626");
      }
      break;

    case "error":
      addLogEntry(event.agent || "System", `Error: ${event.message}`, "#dc2626");
      updateAgentStatus(event.agent, "error");
      break;
  }
}

function handlePipelineComplete(event) {
  const badge = document.getElementById("statusBadge");
  badge.className = "header__badge complete";
  badge.querySelector("span:last-child").textContent = `Done in ${event.elapsed}s`;

  briefingHtml = event.html || "";
  if (briefingHtml) {
    renderBriefing(briefingHtml, true);
  }

  if (event.delivered) {
    showToast("Briefing delivered via email");
  } else if (event.delivery_message) {
    showToast(event.delivery_message);
  }

  if (event.history_id) {
    selectedHistoryId = event.history_id;
    loadHistory(event.history_id);
  } else {
    loadHistory();
  }

  addLogEntry("System", `All agents complete - pipeline finished in ${event.elapsed}s`, "#22c55e");
}

function finishPipeline() {
  isRunning = false;
  clearInterval(timerInterval);

  const btn = document.getElementById("deployBtn");
  btn.disabled = false;
  btn.classList.remove("loading");
  btn.querySelector(".btn-deploy__text").textContent = "Deploy Crew";
}

function resetAgentCards() {
  const cards = document.querySelectorAll(".agent-card");
  cards.forEach((card) => {
    card.classList.remove("working", "done", "error");
    const status = card.querySelector(".agent-card__status");
    status.className = "agent-card__status agent-card__status--idle";
    status.textContent = "idle";
  });
}

function updateAgentStatus(agentName, status) {
  const card = document.querySelector(`.agent-card[data-agent="${agentName}"]`);
  if (!card) return;

  card.classList.remove("working", "done", "error");
  card.classList.add(status);

  const statusEl = card.querySelector(".agent-card__status");
  statusEl.className = `agent-card__status agent-card__status--${status}`;
  statusEl.textContent = status;
}

function addLogEntry(agent, message, color) {
  const feed = document.getElementById("activityFeed");
  const elapsed = startTime ? ((Date.now() - startTime) / 1000).toFixed(1) : "0.0";

  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `
    <span class="log-entry__time">${elapsed}s</span>
    <span class="log-entry__agent" style="color: ${color}">[${agent}]</span>
    <span class="log-entry__msg">${escapeHtml(message)}</span>
  `;

  feed.appendChild(entry);
  feed.scrollTop = feed.scrollHeight;
}

function updateTimer() {
  if (!startTime) return;
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const timerEl = document.getElementById("timerDisplay");
  if (timerEl) timerEl.textContent = `${elapsed}s`;
}

function renderBriefing(html, shouldScroll = false) {
  const briefingPanel = document.getElementById("briefingPanel");
  briefingPanel.style.display = "block";

  const iframe = document.getElementById("briefingFrame");
  const doc = iframe.contentDocument || iframe.contentWindow.document;
  doc.open();
  doc.write(html || "<p>No briefing available</p>");
  doc.close();

  if (shouldScroll) {
    setTimeout(() => {
      briefingPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 350);
  }
}

function downloadBriefing() {
  if (!briefingHtml) return showToast("No briefing to download");

  const blob = new Blob([briefingHtml], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ai-research-briefing.html";
  a.click();
  URL.revokeObjectURL(url);
  showToast("Briefing downloaded");
}

function copyBriefing() {
  if (!briefingHtml) return showToast("No briefing to copy");

  navigator.clipboard.writeText(briefingHtml).then(() => {
    showToast("HTML copied to clipboard");
  });
}

async function loadHistory(highlightId = null) {
  try {
    const response = await fetch("/api/history?limit=25");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    historyEntries = payload.items || [];
    renderHistoryList(highlightId || selectedHistoryId);
  } catch (err) {
    const listEl = document.getElementById("historyList");
    if (listEl) {
      listEl.innerHTML = `<div class="history-empty">Failed to load history: ${escapeHtml(err.message)}</div>`;
    }
  }
}

function renderHistoryList(highlightId = null) {
  const listEl = document.getElementById("historyList");
  if (!listEl) return;

  if (!historyEntries.length) {
    listEl.innerHTML = '<div class="history-empty">No history yet. Run the crew to generate your first briefing.</div>';
    return;
  }

  listEl.innerHTML = "";
  historyEntries.forEach((item) => {
    const row = document.createElement("div");
    row.className = `history-item ${item.id === highlightId ? "history-item--active" : ""}`;

    const status = item.delivered ? "Delivered" : "Saved";
    const deliveryText = item.delivery_message ? escapeHtml(item.delivery_message) : "";
    const createdAt = formatDateTime(item.created_at);

    row.innerHTML = `
      <div class="history-item__main">
        <div class="history-item__topic">${escapeHtml(item.topic || "Untitled")}</div>
        <div class="history-item__meta">
          <span>#${item.id}</span>
          <span>${createdAt}</span>
          <span>${Number(item.elapsed_seconds || 0).toFixed(1)}s</span>
          <span class="history-pill ${item.delivered ? "history-pill--ok" : "history-pill--idle"}">${status}</span>
        </div>
        ${deliveryText ? `<div class="history-item__delivery">${deliveryText}</div>` : ""}
      </div>
      <button class="btn-action history-item__open" title="Open this briefing">Open</button>
    `;

    row.querySelector(".history-item__open").addEventListener("click", () => openHistoryEntry(item.id));
    listEl.appendChild(row);
  });
}

async function openHistoryEntry(entryId) {
  try {
    const response = await fetch(`/api/history/${entryId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const entry = await response.json();

    selectedHistoryId = entry.id;
    briefingHtml = entry.html || "";
    renderBriefing(briefingHtml, true);

    const topicInput = document.getElementById("topicInput");
    if (topicInput && entry.topic) {
      topicInput.value = entry.topic;
      const charCount = document.getElementById("charCount");
      if (charCount) charCount.textContent = `${entry.topic.length}/150`;
    }

    renderHistoryList(selectedHistoryId);
    showToast(`Opened history #${entry.id}`);
  } catch (err) {
    showToast(`Unable to open history entry: ${err.message}`);
  }
}

function formatDateTime(value) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString();
}

function showToast(message) {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("hiding");
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    startPipeline();
  }
});

window.addEventListener("load", async () => {
  const sessionIsValid = await verifySessionOrRedirect();
  if (!sessionIsValid) return;

  // Set user profile
  const userName = localStorage.getItem('user_name');
  if (userName) {
    const displayEl = document.getElementById('displayName');
    if (displayEl) displayEl.textContent = userName;
  }

  try {
    const resp = await fetch("/api/health");
    const data = await resp.json();
    if (!data.groq_configured) {
      showToast("GROQ_API_KEY not configured - add it to your .env file");
    }
  } catch (e) {
    showToast("Backend not reachable - is the Flask server running?");
  }

  const topicInput = document.getElementById("topicInput");
  if (topicInput) {
    topicInput.addEventListener("input", function () {
      document.getElementById("charCount").textContent = this.value.length + "/150";
    });
  }

  await loadHistory();
});
