/** Voice Lab panel: test microphone analysis only; never feeds /alerts. */

const BANNER_TEXT = "TEST MICROPHONE - not radio, not evidence";

function $(sel) {
  return document.querySelector(sel);
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

async function refreshVoiceLabStatus() {
  const micNote = $("#voiceLabMicNote");
  if (!micNote) return;
  try {
    const status = await fetch("/voice-lab/status").then((r) => r.json());
    micNote.textContent = status.mic_enabled
      ? "Local mic capture enabled (WICHITA_VOICE_LAB_MIC)."
      : "Upload a WAV clip, or set WICHITA_VOICE_LAB_MIC=1 for a short mic capture.";
  } catch {
    micNote.textContent = "Voice Lab API unavailable.";
  }
}

async function runVoiceLabAnalyze({ file, useMic }) {
  const out = $("#voiceLabOutput");
  const stressEl = $("#voiceLabStress");
  if (out) out.textContent = "Analyzing…";
  if (stressEl) stressEl.textContent = "—";

  const form = new FormData();
  if (useMic) {
    form.append("use_mic", "true");
  } else if (file) {
    form.append("file", file, file.name);
  } else {
    if (out) out.textContent = "Choose a WAV file or enable mic capture.";
    return;
  }

  const response = await fetch("/voice-lab/analyze", { method: "POST", body: form });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (out) out.textContent = body.detail || `Analysis failed (${response.status})`;
    return;
  }

  if (stressEl && body.stress) {
    stressEl.textContent = `${body.stress.stress_score}% (${body.stress.alert_level})`;
  }
  if (out) out.textContent = formatJson(body);
}

export function initVoiceLab() {
  const banner = $("#voiceLabBanner");
  if (banner) banner.textContent = BANNER_TEXT;

  refreshVoiceLabStatus();

  $("#voiceLabUploadBtn")?.addEventListener("click", () => {
    const input = $("#voiceLabFile");
    const file = input?.files?.[0];
    runVoiceLabAnalyze({ file, useMic: false }).catch((err) => {
      const out = $("#voiceLabOutput");
      if (out) out.textContent = String(err);
    });
  });

  $("#voiceLabMicBtn")?.addEventListener("click", () => {
    runVoiceLabAnalyze({ useMic: true }).catch((err) => {
      const out = $("#voiceLabOutput");
      if (out) out.textContent = String(err);
    });
  });
}

export function initAlertReview() {
  const list = $("#alertReviewList");
  if (!list) return;

  async function loadAlerts() {
    list.innerHTML = "";
    let rows = [];
    try {
      rows = await fetch("/alerts?limit=50").then((r) => r.json());
    } catch {
      list.innerHTML = "<li class=\"muted\">Could not load alerts.</li>";
      return;
    }

    const pending = rows.filter((row) => row.review_status === "pending_review");
    if (!pending.length) {
      list.innerHTML = "<li class=\"muted\">No alerts pending review.</li>";
      return;
    }

    for (const row of pending) {
      const li = document.createElement("li");
      li.className = "alert-review-item";
      const title = document.createElement("div");
      title.className = "alert-review-title";
      title.textContent = row.title;
      const meta = document.createElement("div");
      meta.className = "muted small";
      const stress = row.metadata?.stress_score;
      meta.textContent = [
        row.severity,
        row.frequency_mhz ? `${row.frequency_mhz} MHz` : null,
        stress != null ? `stress ${stress}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
      const actions = document.createElement("div");
      actions.className = "alert-review-actions";
      const confirmBtn = document.createElement("button");
      confirmBtn.type = "button";
      confirmBtn.className = "timeline-more";
      confirmBtn.textContent = "Confirm";
      confirmBtn.dataset.testId = `alert-confirm-${row.id}`;
      confirmBtn.addEventListener("click", async () => {
        await fetch(`/alerts/${row.id}/confirm`, { method: "POST" });
        loadAlerts();
      });
      const dismissBtn = document.createElement("button");
      dismissBtn.type = "button";
      dismissBtn.className = "timeline-more";
      dismissBtn.textContent = "Dismiss";
      dismissBtn.dataset.testId = `alert-dismiss-${row.id}`;
      dismissBtn.addEventListener("click", async () => {
        await fetch(`/alerts/${row.id}/dismiss`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ note: "Dismissed from dashboard" }),
        });
        loadAlerts();
      });
      actions.append(confirmBtn, dismissBtn);
      li.append(title, meta, actions);
      list.append(li);
    }
  }

  loadAlerts();
  setInterval(loadAlerts, 30000);
}
