import { test, expect } from "@playwright/test";
import path from "node:path";

const ARTIFACTS = process.env.WICHITA_ARTIFACTS || "/opt/cursor/artifacts";
const STEPS = ["email", "link", "code", "verify"];

async function computedDisplay(locator) {
  return locator.evaluate((node) => window.getComputedStyle(node).display);
}

async function assertOnlyStepVisible(page, activeStep) {
  for (const step of STEPS) {
    const el = page.locator(`[data-auth-step="${step}"]`);
    const display = await computedDisplay(el);
    if (step === activeStep) {
      expect(display).not.toBe("none");
      await expect(el).toBeVisible();
    } else {
      expect(display).toBe("none");
    }
  }
}

test.describe("passwordless auth gate steps", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/dashboard/playwright/fixtures/auth_gate_harness.html");
    await expect(page.locator('[data-auth-step="email"]')).toBeVisible();
  });

  for (const step of STEPS) {
    test(`only ${step} step is displayed`, async ({ page }) => {
      await page.evaluate((s) => window.__wichitaAuthUi.setView(s), step);
      await assertOnlyStepVisible(page, step);
      await page.screenshot({
        path: path.join(ARTIFACTS, `auth-gate-step-${step}.png`),
        fullPage: true,
      });
    });
  }

  test("initial load shows email step only", async ({ page }) => {
    await assertOnlyStepVisible(page, "email");
    await expect(page.locator("#authEmail")).toBeVisible();
    await expect(page.locator("#authCode")).toBeHidden();
    await expect(page.getByText("Check your email for a sign-in link.")).toBeHidden();
    await expect(page.getByText("Completing sign-in…")).toBeHidden();
  });
});
