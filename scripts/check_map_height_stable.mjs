#!/usr/bin/env node
/**
 * Playwright: harbour map SVG height must stay stable over 10s at 390x844.
 * Usage: node scripts/check_map_height_stable.mjs [baseUrl]
 */
import { chromium } from "playwright";

const base = process.argv[2] || "http://127.0.0.1:8000/";
const viewport = { width: 390, height: 844 };

const browser = await chromium.launch();
const page = await browser.newPage({ viewport });
await page.goto(base, { waitUntil: "networkidle", timeout: 90000 });
await page.waitForSelector(".harbour-svg", { timeout: 30000 });
await page.waitForTimeout(2000);

const readHeight = async () =>
  page.evaluate(() => {
    const svg = document.querySelector(".harbour-svg");
    const host = document.querySelector("#harbourMap");
    return {
      svg: svg ? Math.round(svg.getBoundingClientRect().height) : 0,
      host: host ? Math.round(host.getBoundingClientRect().height) : 0,
    };
  });

const h0 = await readHeight();
if (h0.svg < 100 || h0.host < 100) {
  console.error("Map too small at start:", h0);
  process.exit(1);
}

await page.waitForTimeout(10_000);
const h1 = await readHeight();

const driftSvg = Math.abs(h1.svg - h0.svg);
const driftHost = Math.abs(h1.host - h0.host);
const maxDrift = 4;

if (driftSvg > maxDrift || driftHost > maxDrift) {
  console.error("Map height drifted:", { h0, h1, driftSvg, driftHost });
  process.exit(1);
}

console.log("OK map height stable:", h0, "->", h1);
await browser.close();
