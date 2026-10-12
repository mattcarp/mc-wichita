/**
 * Auth gate vs dashboard shell visibility (shared by clerk_gate.js and tests).
 */

export function setAppVisible(visible) {
  const shell = document.getElementById("appShell");
  const gate = document.getElementById("authGate");
  document.body.classList.toggle("auth-pending", !visible);
  document.body.classList.toggle("dashboard-ready", visible);
  if (shell) {
    shell.hidden = !visible;
    shell.setAttribute("aria-hidden", visible ? "false" : "true");
  }
  if (gate) {
    gate.hidden = visible;
    gate.setAttribute("aria-hidden", visible ? "true" : "false");
  }
}

/** @param {HTMLElement | null} gate */
export function gateComputedDisplayed(gate) {
  if (!gate || gate.hidden) return false;
  const style = window.getComputedStyle(gate);
  return style.display !== "none" && style.visibility !== "hidden";
}
