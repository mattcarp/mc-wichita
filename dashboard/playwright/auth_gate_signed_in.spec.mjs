import { test, expect } from "@playwright/test";

async function assertGateHidden(page) {
  const gate = page.locator("#authGate");
  await expect(gate).toBeHidden();
  const display = await gate.evaluate((el) => window.getComputedStyle(el).display);
  expect(display).toBe("none");
  await expect(page.locator(".auth-gate-brand")).toBeHidden();
}

test.describe("signed-in auth gate shell", () => {
  test("mocked Clerk.user hides gate and shows dashboard header", async ({ page }) => {
    await page.goto("/dashboard/playwright/fixtures/clerk_signed_in_harness.html");
    await assertGateHidden(page);
    await expect(page.locator("#headerLive")).toBeVisible();
    await expect(page.locator(".wichita-user-name")).toHaveText("Mattie");
    await expect(page.locator("#dashboardProbe")).toBeVisible();
    await expect(page.locator("body")).toHaveClass(/dashboard-ready/);
    await expect(page.locator("body")).not.toHaveClass(/auth-pending/);
    await expect(page.locator("#appShell")).toBeVisible();
  });

  test("reload with existing session keeps gate hidden", async ({ page }) => {
    await page.goto("/dashboard/playwright/fixtures/clerk_signed_in_reload_harness.html");
    await assertGateHidden(page);
    await expect(page.locator("#headerLive")).toBeVisible();
    await expect(page.locator(".wichita-user-name")).toHaveText("Mattie");
  });
});
