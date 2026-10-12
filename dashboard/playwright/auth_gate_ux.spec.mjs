import { test, expect } from "@playwright/test";
import {
  assertOnlyAuthStep,
  assertGateHidden,
  assertGateVisible,
  assertDashboardVisible,
  assertDashboardHidden,
  assertUserMenuAbsent,
  assertNoHorizontalOverflow,
  attachConsoleErrorCollector,
  expectNoConsoleErrors,
  saveShot,
  waitVisualHarnessReady,
  SIGNED_OUT_RELOAD_HARNESS,
} from "./helpers/auth_visibility.mjs";

test.describe("auth gate UX (mocked Clerk)", () => {
  let consoleErrors;

  test.beforeEach(async ({ page }) => {
    consoleErrors = attachConsoleErrorCollector(page);
  });

  test.afterEach(() => {
    expectNoConsoleErrors(consoleErrors);
  });

  test.describe("user menu absent when signed out", () => {
    test("initial signed-out gate", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await assertUserMenuAbsent(page);
      await assertGateVisible(page);
      await assertOnlyAuthStep(page, "email");
    });

    test("after full page reload while signed out", async ({ page }) => {
      await page.goto(SIGNED_OUT_RELOAD_HARNESS);
      await page.waitForFunction(() => window.__wichitaAuthReady === true);
      await assertUserMenuAbsent(page);
      await page.reload();
      await page.waitForFunction(() => window.__wichitaAuthReady === true);
      await assertUserMenuAbsent(page);
      await assertGateVisible(page);
      await assertOnlyAuthStep(page, "email");
    });

    test("after sign-out from signed-in session", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await page.locator("#authCode").fill("123456");
      await page.getByRole("button", { name: "Verify" }).click();
      await assertGateHidden(page);
      await expect(page.getByTestId("wichita-user-trigger")).toBeVisible();
      await page.getByTestId("wichita-user-trigger").click();
      await page.getByTestId("wichita-user-signout").click();
      await assertGateVisible(page);
      await assertOnlyAuthStep(page, "email");
      await assertDashboardHidden(page);
      await assertUserMenuAbsent(page);
    });

    test("sign-out hard-resets when Clerk listener does not fire", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await page.locator("#authCode").fill("123456");
      await page.getByRole("button", { name: "Verify" }).click();
      await assertGateHidden(page);
      await page.evaluate(() => window.__wichitaMockClerk.setSignOutNotifiesListener(false));
      await page.getByTestId("wichita-user-trigger").click();
      await page.getByTestId("wichita-user-signout").click();
      await assertGateVisible(page);
      await assertOnlyAuthStep(page, "email");
      await assertDashboardHidden(page);
      await assertUserMenuAbsent(page);
      await expect(page.locator("#authEmail")).toBeFocused();
    });
  });

  test.describe("keyboard flow and focus", () => {
    test("Enter submits email; code step focuses input", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await expect(page.locator("#authEmail")).toBeFocused();
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.locator("#authEmail").press("Enter");
      await assertOnlyAuthStep(page, "link");
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await assertOnlyAuthStep(page, "code");
      await expect(page.locator("#authCode")).toBeFocused();
      await page.locator("#authCode").fill("123456");
      await page.locator("#authCode").press("Enter");
      await assertGateHidden(page);
      await assertDashboardVisible(page);
    });

    test("email step refocuses input after restart", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.getByRole("button", { name: "Use a different email" }).click();
      await assertOnlyAuthStep(page, "email");
      await expect(page.locator("#authEmail")).toBeFocused();
    });
  });

  test.describe("loading and disabled controls", () => {
    test("email submit shows busy state while mock is slow", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.evaluate(() => window.__wichitaMockClerk.setOperationDelay(400));
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      const submit = page.getByRole("button", { name: "Continue with email" });
      await submit.click();
      const shell = page.locator(".auth-form-shell");
      await expect(shell).toHaveAttribute("aria-busy", "true");
      await expect(submit).toBeDisabled();
      await expect(submit).toHaveAttribute("aria-busy", "true");
      await assertOnlyAuthStep(page, "email");
      await expect(page.getByText("Check your email for a sign-in link.")).toBeVisible();
      await expect(shell).toHaveAttribute("aria-busy", "false");
      await assertOnlyAuthStep(page, "link");
      await page.evaluate(() => window.__wichitaMockClerk.setOperationDelay(0));
    });

    test("code verify disabled while verifying", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await page.evaluate(() => window.__wichitaMockClerk.setOperationDelay(350));
      await page.locator("#authCode").fill("123456");
      const verify = page.getByRole("button", { name: "Verify" });
      await verify.click();
      await expect(page.locator(".auth-form-shell")).toHaveAttribute("aria-busy", "true");
      await expect(verify).toBeDisabled();
      await assertGateHidden(page);
      await page.evaluate(() => window.__wichitaMockClerk.setOperationDelay(0));
    });
  });

  test.describe("error states", () => {
    test("HTTP 429 on signIn.create shows rate limit on email step", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.evaluate(() => window.__wichitaMockClerk.setRateLimitOnCreate(true));
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      const submit = page.getByRole("button", { name: "Continue with email" });
      await submit.click();
      const status = page.locator('[data-auth-notice="true"].auth-form-status-visible');
      await expect(status).toBeVisible();
      await expect(status).toHaveText(
        "Too many sign-in attempts. Please wait a few minutes and try again.",
      );
      await assertOnlyAuthStep(page, "email");
      await expect(submit).toBeEnabled();
      await expect(page.locator(".auth-form-shell")).toHaveAttribute("aria-busy", "false");
      await page.evaluate(() => window.__wichitaMockClerk.setRateLimitOnCreate(false));
    });

    test("HTTP 429 on prepareFirstFactor shows rate limit on email step", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.evaluate(() => window.__wichitaMockClerk.setRateLimitOnPrepareLink(true));
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      const submit = page.getByRole("button", { name: "Continue with email" });
      await submit.click();
      const status = page.locator('[data-auth-notice="true"].auth-form-status-visible');
      await expect(status).toBeVisible();
      await expect(status).toHaveText(
        "Too many sign-in attempts. Please wait a few minutes and try again.",
      );
      await assertOnlyAuthStep(page, "email");
      await expect(submit).toBeEnabled();
      await page.evaluate(() => window.__wichitaMockClerk.setRateLimitOnPrepareLink(false));
    });

    test("incorrect code shows status and stays on code step", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await page.locator("#authCode").fill("999999");
      await page.getByRole("button", { name: "Verify" }).click();
      const status = page.locator('[data-auth-notice="true"].auth-form-status-visible');
      await expect(status).toBeVisible();
      await expect(status).toContainText(/incorrect code/i);
      await assertOnlyAuthStep(page, "code");
      await assertUserMenuAbsent(page);
    });

    test("rate limit on use-code shows error on link step", async ({ page }) => {
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.evaluate(() => window.__wichitaMockClerk.setRateLimitOnCode(true));
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await expect(page.locator(".auth-form-status-visible")).toContainText(
        /too many sign-in attempts/i,
      );
      await assertOnlyAuthStep(page, "link");
    });
  });

  for (const vp of [
    { id: "mobile", width: 390, height: 844 },
    { id: "desktop", width: 1280, height: 720 },
  ]) {
    test(`viewport ${vp.id}: signed-out gate, no overflow, screenshot`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await waitVisualHarnessReady(page);
      await assertUserMenuAbsent(page);
      await assertNoHorizontalOverflow(page);
      await saveShot(page, `auth-ux-${vp.id}-signed-out.png`);
    });

    test(`viewport ${vp.id}: signed-in dashboard, no overflow, screenshot`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await waitVisualHarnessReady(page);
      await page.locator("#authEmail").fill("mattie@wichitawire.com");
      await page.getByRole("button", { name: "Continue with email" }).click();
      await page.getByRole("button", { name: "Use a code instead" }).click();
      await page.locator("#authCode").fill("123456");
      await page.getByRole("button", { name: "Verify" }).click();
      await assertGateHidden(page);
      await assertNoHorizontalOverflow(page);
      await saveShot(page, `auth-ux-${vp.id}-signed-in.png`);
    });
  }
});
