/** Aircraft of interest — watch list, lookup, pinned roster integration. */

import { esc, debouncedLookup, renderInterestCandidates } from "./things_of_interest.js?v=20261024-interest";

function $(sel) {
  return document.querySelector(sel);
}

let onListChange = () => {};

export function setAircraftOfInterestRefresh(fn) {
  onListChange = fn || (() => {});
}

function candidateRow(c) {
  const key = c.hex || c.hex_display;
  return `<button type="button" class="interest-candidate" data-interest-key="${esc(key)}" data-test-id="air-interest-candidate-${esc(key)}">
    <strong>${esc(c.display_name || c.callsign || c.hex_display)}</strong>
    <span class="mono muted">${esc(c.hex_display)}${c.registration ? ` · ${esc(c.registration)}` : ""}${c.callsign ? ` · ${esc(c.callsign)}` : ""}</span>
    <span class="muted small">${esc((c.sources || []).join(", "))}</span>
  </button>`;
}

export function initAircraftOfInterest() {
  const addBtn = $("#airInterestAdd");
  const dialog = $("#airInterestDialog");
  if (!addBtn || !dialog) return;

  const queryInput = $("#airInterestQuery");
  const candidatesEl = $("#airInterestCandidates");
  const confirmPanel = $("#airInterestConfirm");
  const confirmName = $("#airInterestConfirmName");
  const confirmMeta = $("#airInterestConfirmMeta");
  const statusEl = $("#airInterestStatus");
  let picked = null;

  function resetDialog() {
    picked = null;
    if (queryInput) queryInput.value = "";
    if (candidatesEl) candidatesEl.innerHTML = "";
    if (confirmPanel) confirmPanel.hidden = true;
    if (statusEl) statusEl.textContent = "";
  }

  addBtn.addEventListener("click", () => {
    resetDialog();
    dialog.showModal();
  });

  dialog.querySelectorAll("[data-interest-cancel]").forEach((btn) => {
    btn.addEventListener("click", () => dialog.close());
  });

  debouncedLookup(queryInput, async (q) => {
    if (q.length < 2) {
      if (candidatesEl) candidatesEl.innerHTML = "";
      return;
    }
    try {
      const res = await fetch("/api/interests/flights/lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      const candidates = (data.candidates || []).map((c) => ({ ...c, interestKey: c.hex }));
      renderInterestCandidates(candidatesEl, candidates, candidateRow, (row) => {
        picked = row;
        if (confirmPanel) confirmPanel.hidden = false;
        if (confirmName) confirmName.textContent = row.display_name || row.callsign || row.hex_display;
        if (confirmMeta) {
          confirmMeta.textContent = `${row.hex_display}${row.registration ? ` · ${row.registration}` : ""}`;
        }
      });
    } catch {
      if (statusEl) statusEl.textContent = "Lookup failed.";
    }
  });

  $("#airInterestSave")?.addEventListener("click", async () => {
    if (!picked) return;
    try {
      const res = await fetch("/api/interests/flights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hex: picked.hex,
          callsign: picked.callsign || null,
          registration: picked.registration || null,
          label: picked.display_name || picked.callsign || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || String(res.status));
      }
      dialog.close();
      onListChange();
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message || "Could not save.";
    }
  });

  document.body.addEventListener("click", async (ev) => {
    const btn = ev.target.closest?.("[data-air-interest-remove]");
    if (!btn) return;
    const id = btn.getAttribute("data-air-interest-remove");
    if (!id) return;
    try {
      await fetch(`/api/interests/flights/${encodeURIComponent(id)}`, { method: "DELETE" });
      onListChange();
    } catch {
      /* ignore */
    }
  });
}
