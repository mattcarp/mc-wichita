import path from "node:path";

export const ARTIFACTS = "/opt/cursor/artifacts";
export const AUTH_STEPS = ["email", "link", "code", "verify"];

export async function stepDisplay(page, step) {
  const el = page.locator(`[data-auth-step="${step}"]`);
  return el.evaluate((node) => window.getComputedStyle(node).display);
}

export async function assertOnlyAuthStep(page, activeStep) {
  for (const step of AUTH_STEPS) {
    const display = await stepDisplay(page, step);
    if (step === activeStep) {
      if (display === "none") throw new Error(`expected step ${step} visible, got display:none`);
    } else if (display !== "none") {
      throw new Error(`expected step ${step} hidden, got ${display}`);
    }
  }
}

export async function assertGateHidden(page) {
  const gate = page.locator("#authGate");
  await gate.waitFor({ state: "hidden" });
  const display = await gate.evaluate((el) => window.getComputedStyle(el).display);
  if (display !== "none") throw new Error(`gate display expected none, got ${display}`);
}

export async function assertGateVisible(page) {
  const gate = page.locator("#authGate");
  await gate.waitFor({ state: "visible" });
  const display = await gate.evaluate((el) => window.getComputedStyle(el).display);
  if (display === "none") throw new Error("gate should be visible");
}

export async function assertDashboardVisible(page) {
  const shell = page.locator("#appShell");
  await shell.waitFor({ state: "visible" });
  const display = await shell.evaluate((el) => window.getComputedStyle(el).display);
  if (display === "none") throw new Error("app shell should be visible");
  await page.locator("#dashboardProbe").waitFor({ state: "visible" });
}

export async function assertDashboardHidden(page) {
  const shell = page.locator("#appShell");
  const hidden = await shell.evaluate((el) => el.hidden || window.getComputedStyle(el).display === "none");
  if (!hidden) throw new Error("app shell should be hidden");
}

export async function saveShot(page, filename) {
  await page.screenshot({ path: path.join(ARTIFACTS, filename), fullPage: true });
}
