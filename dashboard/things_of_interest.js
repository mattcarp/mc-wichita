/** Shared helpers for boats & aircraft “of interest” lookup dialogs. */

export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

export function debouncedLookup(inputEl, onQuery, delayMs = 350) {
  let timer = null;
  inputEl?.addEventListener("input", () => {
    clearTimeout(timer);
    const q = inputEl.value.trim();
    timer = setTimeout(() => onQuery(q), delayMs);
  });
}

export function renderInterestCandidates(listEl, candidates, renderRow, onPick) {
  if (!candidates.length) {
    listEl.innerHTML = "<p class=\"muted small\">No match in live feed. Try ICAO hex, call sign, or registration.</p>";
    return;
  }
  listEl.innerHTML = candidates.map(renderRow).join("");
  listEl.querySelectorAll(".interest-candidate").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-interest-key");
      const row = candidates.find((x) => String(x.interestKey) === id);
      onPick(row);
    });
  });
}
