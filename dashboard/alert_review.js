/** Human-review alert queue: every alert waits for a person; nothing acts on its own. */

function $(sel) {
  return document.querySelector(sel);
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
