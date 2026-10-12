import { test, expect } from "@playwright/test";
import {
  assertOnlyAuthStep,
  assertGateHidden,
  assertGateVisible,
  assertDashboardVisible,
  assertDashboardHidden,
  assertUserMenuAbsent,
  saveShot,
  waitVisualHarnessReady,
} from "./helpers/auth_visibility.mjs";

async function waitReady(page) {
  await waitVisualHarnessReady(page);
}

async function ui(page) {
  return page.evaluate(() => document.querySelector("#clerkSignIn")?.__wichitaAuthUi);
}

test.describe("auth gate visual e2e (mocked Clerk)", () => {
  test("signed-out gate shows email step only", async ({ page }) => {
    await waitReady(page);
    await assertGateVisible(page);
    await assertOnlyAuthStep(page, "email");
    await assertDashboardHidden(page);
    await assertUserMenuAbsent(page);
    await saveShot(page, "auth-visual-01-signed-out-email.png");
  });

  test("link-sent step only", async ({ page }) => {
    await waitReady(page);
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    await page.getByRole("button", { name: "Continue with email" }).click();
    await assertOnlyAuthStep(page, "link");
    await expect(page.getByText("Check your email for a sign-in link.")).toBeVisible();
    await saveShot(page, "auth-visual-02-link-sent.png");
  });

  test("code step only", async ({ page }) => {
    await waitReady(page);
    await page.evaluate(() => {
      const ui = document.querySelector("#clerkSignIn").__wichitaAuthUi;
      ui.setView("code");
    });
    await assertOnlyAuthStep(page, "code");
    await saveShot(page, "auth-visual-03-code-step.png");
  });

  test("rate limit error on link step stays clear", async ({ page }) => {
    await waitReady(page);
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    await page.getByRole("button", { name: "Continue with email" }).click();
    await assertOnlyAuthStep(page, "link");
    await page.evaluate(() => window.__wichitaMockClerk.setRateLimitOnCode(true));
    await page.getByRole("button", { name: "Use a code instead" }).click();
    const status = page.locator(".auth-form-status-visible");
    await expect(status).toBeVisible();
    await expect(status).toContainText(/too many requests/i);
    await assertOnlyAuthStep(page, "link");
    await saveShot(page, "auth-visual-04-rate-limit-on-link.png");
  });

  test("successful code sign-in shows dashboard and first name", async ({ page }) => {
    await waitReady(page);
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    await page.getByRole("button", { name: "Continue with email" }).click();
    await page.getByRole("button", { name: "Use a code instead" }).click();
    await assertOnlyAuthStep(page, "code");
    await page.locator("#authCode").fill("123456");
    await page.getByRole("button", { name: "Verify" }).click();
    await assertGateHidden(page);
    await assertDashboardVisible(page);
    await expect(page.getByTestId("wichita-user-trigger")).toBeVisible();
    await expect(page.locator(".wichita-user-name")).toHaveText("Mattie");
    await saveShot(page, "auth-visual-05-signed-in-dashboard.png");
  });

  test("reload while signed in opens dashboard directly", async ({ page }) => {
    await page.goto("/dashboard/playwright/fixtures/clerk_signed_in_reload_harness.html");
    await page.waitForFunction(() => window.__wichitaAuthReady === true || document.body.classList.contains("dashboard-ready"));
    await assertGateHidden(page);
    await assertDashboardVisible(page);
    await saveShot(page, "auth-visual-06-reload-signed-in.png");
  });

  test("user menu opens with email and sign out", async ({ page }) => {
    await waitReady(page);
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    await page.getByRole("button", { name: "Continue with email" }).click();
    await page.getByRole("button", { name: "Use a code instead" }).click();
    await page.locator("#authCode").fill("123456");
    await page.getByRole("button", { name: "Verify" }).click();
    await page.getByTestId("wichita-user-trigger").click();
    const menu = page.getByTestId("wichita-user-dropdown");
    await expect(menu).toBeVisible();
    await expect(menu).toContainText("mattie@wichitawire.com");
    await expect(page.getByTestId("wichita-user-signout")).toBeVisible();
    const menuDisplay = await menu.evaluate((el) => window.getComputedStyle(el).display);
    expect(menuDisplay).not.toBe("none");
    await saveShot(page, "auth-visual-07-user-menu-open.png");
  });

  test("sign out returns to email-only gate", async ({ page }) => {
    await waitReady(page);
    await page.locator("#authEmail").fill("mattie@wichitawire.com");
    await page.getByRole("button", { name: "Continue with email" }).click();
    await page.getByRole("button", { name: "Use a code instead" }).click();
    await page.locator("#authCode").fill("123456");
    await page.getByRole("button", { name: "Verify" }).click();
    await assertGateHidden(page);
    await page.getByTestId("wichita-user-trigger").click();
    await page.getByTestId("wichita-user-signout").click();
    await assertGateVisible(page);
    await assertOnlyAuthStep(page, "email");
    await assertDashboardHidden(page);
    await assertUserMenuAbsent(page);
    await saveShot(page, "auth-visual-08-signed-out-after-signout.png");
  });
});
