import path from "node:path";
import { expect } from "@playwright/test";

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

/** Account chip must not exist before sign-in or after sign-out. */
export async function assertUserMenuAbsent(page) {
  const host = page.locator("#wichitaUserMenu");
  await expect(host).toBeAttached();
  await expect(host).toBeHidden();
  const hostState = await host.evaluate((el) => ({
    childCount: el.children.length,
    ariaHidden: el.getAttribute("aria-hidden"),
    text: el.textContent?.trim() ?? "",
  }));
  expect(hostState.childCount).toBe(0);
  expect(hostState.text).toBe("");
  expect(hostState.ariaHidden === "true" || hostState.ariaHidden === "").toBeTruthy();
  await expect(page.locator(".wichita-user-menu")).toHaveCount(0);
  await expect(page.locator(".wichita-user-trigger")).toHaveCount(0);
  await expect(page.locator(".wichita-user-name")).toHaveCount(0);
  await expect(page.locator(".wichita-user-avatar")).toHaveCount(0);
  const bodyText = await page.locator("body").innerText();
  expect(bodyText).not.toMatch(/\bMattie\b/);
}

export async function assertNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth - doc.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
}

export function attachConsoleErrorCollector(page) {
  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err?.message || err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  return errors;
}

export function expectNoConsoleErrors(errors) {
  expect(errors, errors.join("\n")).toEqual([]);
}

export const VISUAL_HARNESS = "/dashboard/playwright/fixtures/visual_auth.harness.html";
export const SIGNED_OUT_RELOAD_HARNESS =
  "/dashboard/playwright/fixtures/clerk_signed_out_reload_harness.html";

export async function waitVisualHarnessReady(page, url = VISUAL_HARNESS) {
  await page.goto(url);
  await page.waitForFunction(() => window.__wichitaAuthReady === true);
}
