#!/usr/bin/env node
/**
 * Playwright screenshots for UI critique 2 verification.
 * Usage:
 *   WICHITA_AIS_FIXTURE_DIR=... WICHITA_CAPTURES_DIRS=... node scripts/check_dashboard_ui_critique2.mjs [baseUrl]
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const base = process.argv[2] || process.env.WICHITA_DASHBOARD_URL || "http://127.0.0.1:8765/";
const outDir = process.env.WICHITA_UI_SCREENSHOT_DIR || path.join("artifacts", "ui-critique-2");

const tabs = ["harbour", "heard", "sky", "recordings", "station"];
const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "phone", width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
];

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();

for (const vp of viewports) {
  const page = await browser.newPage({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: vp.deviceScaleFactor || 1,
    isMobile: vp.isMobile || false,
    hasTouch: vp.hasTouch || false,
  });
  await page.goto(base, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForSelector(".harbour-svg", { timeout: 60000 });

  for (const tab of tabs) {
    await page.click(`.tab-btn[data-tab-target="${tab}"]`, { force: false });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-tab-${tab}.png`), fullPage: false });
  }

  await page.click('.tab-btn[data-tab-target="harbour"]');
  await page.waitForTimeout(800);
  const card = page.locator(".live-ship-card").first();
  if (await card.count()) {
    await card.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-ship-sheet.png`) });
    if (vp.name === "desktop") {
      await page.screenshot({ path: path.join(outDir, `${vp.name}-ship-drawer.png`) });
    }
  }

  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const followCard = page.locator(".live-ship-card").first();
  if (await followCard.count()) {
    await followCard.click();
    await page.waitForTimeout(300);
    await followCard.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(outDir, `${vp.name}-follow.png`) });
  }

  await page.close();
}

console.log("Screenshots written to", outDir);
await browser.close();
