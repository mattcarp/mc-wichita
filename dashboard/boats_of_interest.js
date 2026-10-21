/** Boats of interest — add/remove, lookup, pinned roster integration. */

function $(sel) {
  return document.querySelector(sel);
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

let onListChange = () => {};

export function setBoatsOfInterestRefresh(fn) {
  onListChange = fn || (() => {});
}

async function fetchBoats() {
  const res = await fetch("/api/interests/boats");
  if (!res.ok) throw new Error(String(res.status));
  const data = await res.json();
  return data.boats || [];
}

function renderCandidates(listEl, candidates, onPick) {
  if (!candidates.length) {
    listEl.innerHTML = "<p class=\"muted small\">No match in our heard-ships data or MMSI registry. Try the full nine-digit MMSI.</p>";
    return;
  }
  listEl.innerHTML = candidates
    .map(
      (c) => `<button type="button" class="interest-candidate" data-mmsi="${c.mmsi}" data-test-id="interest-candidate-${c.mmsi}">
        <strong>${esc(c.display_name || c.shipname || `MMSI ${c.mmsi_display}`)}</strong>
        <span class="mono muted">${esc(c.mmsi_display)}${c.callsign ? ` · ${esc(c.callsign)}` : ""}</span>
        <span class="muted small">${esc((c.sources || []).join(", "))}</span>
      </button>`,
    )
    .join("");
  listEl.querySelectorAll(".interest-candidate").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mmsi = Number(btn.getAttribute("data-mmsi"));
      const row = candidates.find((x) => x.mmsi === mmsi);
      onPick(row);
    });
  });
}

export function initBoatsOfInterest() {
  const addBtn = $("#boatInterestAdd");
  const dialog = $("#boatInterestDialog");
  if (!addBtn || !dialog) return;

  const queryInput = $("#boatInterestQuery");
  const candidatesEl = $("#boatInterestCandidates");
  const confirmPanel = $("#boatInterestConfirm");
  const confirmName = $("#boatInterestConfirmName");
  const confirmMeta = $("#boatInterestConfirmMeta");
  const statusEl = $("#boatInterestStatus");
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

  let lookupTimer = null;
  queryInput?.addEventListener("input", () => {
    clearTimeout(lookupTimer);
    const q = queryInput.value.trim();
    if (q.length < 2) {
      if (candidatesEl) candidatesEl.innerHTML = "";
      return;
    }
    lookupTimer = setTimeout(async () => {
      try {
        const res = await fetch("/api/interests/boats/lookup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q }),
        });
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        renderCandidates(candidatesEl, data.candidates || [], (row) => {
          picked = row;
          if (confirmPanel) confirmPanel.hidden = false;
          if (confirmName) {
            confirmName.textContent = row.display_name || row.shipname || `MMSI ${row.mmsi_display}`;
          }
          if (confirmMeta) {
            confirmMeta.textContent = `${row.mmsi_display}${row.callsign ? ` · ${row.callsign}` : ""}`;
          }
        });
      } catch {
        if (statusEl) statusEl.textContent = "Lookup failed.";
      }
    }, 350);
  });

  $("#boatInterestSave")?.addEventListener("click", async () => {
    if (!picked) return;
    try {
      const res = await fetch("/api/interests/boats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mmsi: picked.mmsi,
          label: picked.display_name || picked.shipname || null,
          callsign: picked.callsign || null,
          imo: picked.imo || null,
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
    const btn = ev.target.closest?.("[data-interest-remove]");
    if (!btn) return;
    const id = btn.getAttribute("data-interest-remove");
    if (!id) return;
    try {
      await fetch(`/api/interests/boats/${encodeURIComponent(id)}`, { method: "DELETE" });
      onListChange();
    } catch {
      /* ignore */
    }
  });
}

export { fetchBoats };
