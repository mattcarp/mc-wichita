import { test, expect } from "@playwright/test";
import { CLERK_VERIFICATION_CODE_RATE_LIMIT_BODY } from "../clerk_errors.mjs";
import {
  assertOnlyAuthStep,
  assertGateVisible,
  waitVisualHarnessReady,
} from "./helpers/auth_visibility.mjs";

const PREPARE_HARNESS = "/dashboard/playwright/fixtures/clerk_prepare_429_harness.html";
const RATE_LIMIT_TEXT =
  "Too many sign-in attempts. Please wait a few minutes and try again.";

test.describe("prepare_first_factor HTTP 429 (routed)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(/prepare_first_factor/i, async (route) => {
      await route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify(CLERK_VERIFICATION_CODE_RATE_LIMIT_BODY),
      });
    });
  });

  test("shows rate limit on email step after create succeeds", async ({ page }) => {
    await page.goto(PREPARE_HARNESS);
    await page.waitForFunction(() => window.__wichitaAuthReady === true);
    await assertGateVisible(page);
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    const submit = page.getByRole("button", { name: "Continue with email" });
    await submit.click();
    const status = page.locator('[data-auth-notice="true"].auth-form-status-visible');
    await expect(status).toBeVisible();
    await expect(status).toHaveText(RATE_LIMIT_TEXT);
    await assertOnlyAuthStep(page, "email");
    await expect(submit).toBeEnabled();
    await expect(page.locator("body")).toContainText(RATE_LIMIT_TEXT);
  });
});

test.describe("Clerk listener during sign-in", () => {
  test("prepare 429 survives signIn.create listener (no form remount)", async ({ page }) => {
    await waitVisualHarnessReady(page);
    await page.evaluate(() => {
      window.__wichitaMockClerk.setNotifyOnSignInCreate(true);
      window.__wichitaMockClerk.setRateLimitOnPrepareLink(true);
    });
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    await page.getByRole("button", { name: "Continue with email" }).click();
    const status = page.locator('[data-auth-notice="true"].auth-form-status-visible');
    await expect(status).toHaveText(RATE_LIMIT_TEXT);
    await assertOnlyAuthStep(page, "email");
  });
});
