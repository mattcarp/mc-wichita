import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const base = process.env.BASE_URL || "http://127.0.0.1:8000/";
const outDir = process.env.OUT_DIR || "/opt/cursor/artifacts/screenshots";

const sizes = [
  { name: "desktop-1440x1000", width: 1440, height: 1000 },
  { name: "mobile-390x844", width: 390, height: 844 },
];

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
for (const size of sizes) {
  const page = await browser.newPage({ viewport: { width: size.width, height: size.height } });
  await page.goto(base, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("#harbourMap", { timeout: 30000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${outDir}/gev-harbour-${size.name}.png`, fullPage: false });
  await page.evaluate(() => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    document.querySelector('[data-tab-target="heard"]')?.classList.add("active");
    document.querySelector("#panel-heard")?.classList.add("active");
  });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${outDir}/gev-heard-${size.name}.png`, fullPage: false });
  await page.close();
}
await browser.close();
console.log("saved", sizes.map((s) => s.name).join(", "));
