// Harbour map / side panel render + loading-state tests. Fail on ANY console error or page error.
import { test, expect } from "@playwright/test";

function watch(page) {
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("requestfailed", (r) => errors.push("requestfailed: " + r.url() + " " + (r.failure()?.errorText || "")));
  return errors;
}

test("Harbour map and side panel render real content, no console or page errors", async ({ page }) => {
  const errors = watch(page);
  await page.goto("/", { waitUntil: "load" });
  await page.waitForSelector("#appShell:not([hidden])", { timeout: 20000 });
  // map: SVG with drawn shapes
  await page.waitForSelector("#harbourMap svg path", { state: "attached", timeout: 20000 });
  expect(await page.locator("#harbourMap svg path").count()).toBeGreaterThan(0);
  // header no longer "Checking AIS…"
  await expect(page.locator("#headerLive")).not.toContainText("Checking", { timeout: 20000 });
  // loading indicators gone once data arrived
  await expect(page.locator("#mapLoading")).toBeHidden();
  // side panel has real content (a list of ships or an honest empty message), not a blank box
  const side = page.locator("#mapSideList");
  await expect(side).toBeVisible();
  await expect.poll(async () => (await side.innerText()).trim().length, { timeout: 20000 }).toBeGreaterThan(10);
  expect(await side.innerText()).not.toMatch(/Loading ships/);
  await page.screenshot({ path: "/workspace/live-harbour.png", fullPage: false });
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Harbour shows a loading indicator first, then an error with Retry if the feed fails", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  let fail = true;
  await page.route("**/api/live-ais/snapshot", (route) => (fail ? route.abort("failed") : route.continue()));
  await page.goto("/", { waitUntil: "load" });
  await page.waitForSelector("#appShell:not([hidden])", { timeout: 20000 });
  // never a blank box: either the spinner or the error text is visible in the map area
  await expect(page.locator("#mapLoading")).toBeVisible();
  await expect(page.locator("#mapLoading")).toHaveAttribute("data-state", "error", { timeout: 20000 });
  await expect(page.locator("#mapLoading .load-msg")).toContainText(/could not|timed out/i);
  await expect(page.locator("#sideLoading .load-retry")).toBeVisible();
  // Retry recovers once the feed is back
  fail = false;
  await page.locator("#mapLoading .load-retry").click();
  await expect(page.locator("#mapLoading")).toBeHidden({ timeout: 20000 });
  await expect(page.locator("#headerLive")).not.toContainText("Checking", { timeout: 20000 });
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Heard and Sky tabs render without errors", async ({ page }) => {
  const errors = watch(page);
  await page.goto("/", { waitUntil: "load" });
  await page.waitForSelector("#appShell:not([hidden])", { timeout: 20000 });
  await page.waitForSelector("#harbourMap svg path", { state: "attached", timeout: 20000 }); // app scripts have booted
  for (const tab of ["heard", "sky"]) {
    await page.click(`.tab-btn[data-tab-target="${tab}"]`);
    await page.waitForTimeout(2500);
    const panel = page.locator(`#panel-${tab}`);
    await expect(panel).toBeVisible();
    expect((await panel.innerText()).trim().length).toBeGreaterThan(50);
    await page.screenshot({ path: `/workspace/live-${tab}.png` });
  }
  expect(errors, errors.join("\n")).toEqual([]);
});

test("Incident replay opens from a timeline event and the scrubber moves (if events exist)", async ({ page }) => {
  const errors = watch(page);
  await page.goto("/", { waitUntil: "load" });
  await page.waitForSelector("#appShell:not([hidden])", { timeout: 20000 });
  await page.waitForSelector("#harbourMap svg path", { state: "attached", timeout: 20000 });
  await page.click(".tab-btn[data-tab-target=\"heard\"]").catch(() => {});
  await page.waitForTimeout(3000);
  const rows = page.locator("#timeline li[data-ts]");
  const n = await rows.count();
  test.skip(n === 0, "no timeline events with timestamps on the live site right now");
  await rows.first().click();
  const scrub = page.locator("#incidentScrub");
  await expect(scrub).toBeVisible({ timeout: 20000 });
  const min = Number(await scrub.getAttribute("min"));
  const max = Number(await scrub.getAttribute("max"));
  await scrub.evaluate((el, v) => { el.value = String(v); el.dispatchEvent(new Event("input", { bubbles: true })); }, min);
  await page.waitForTimeout(1500);
  const a = await scrub.inputValue();
  await scrub.evaluate((el, v) => { el.value = String(v); el.dispatchEvent(new Event("input", { bubbles: true })); }, max);
  await page.waitForTimeout(1500);
  expect(await scrub.inputValue()).not.toBe(a);
  await expect(page.locator("#incidentReplayTime")).not.toBeEmpty();
  await page.screenshot({ path: "/workspace/live-replay.png" });
  expect(errors, errors.join("\n")).toEqual([]);
});
