// One Clerk sign-in for the whole run; reused via storageState. Reuses a saved session if still valid.
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const AUTH = path.resolve(".auth");
const STATE = path.join(AUTH, "state.json");
const CODE = path.join(AUTH, "code.txt");

export default async function globalSetup(config) {
  const baseURL = config.projects[0].use.baseURL;
  const launchOptions = config.projects[0].use.launchOptions || {};
  fs.mkdirSync(AUTH, { recursive: true });
  const browser = await chromium.launch(launchOptions);
  try {
    if (fs.existsSync(STATE)) {
      const ctx = await browser.newContext({ storageState: STATE });
      const p = await ctx.newPage();
      await p.goto(baseURL, { waitUntil: "load" });
      const ok = await p.waitForSelector("#appShell:not([hidden])", { timeout: 15000 }).then(() => true).catch(() => false);
      await ctx.close();
      if (ok) return;
    }
    const email = process.env.WICHITA_EMAIL;
    if (!email) throw new Error("Set WICHITA_EMAIL for the one shared sign-in");
    const ctx = await browser.newContext();
    const p = await ctx.newPage();
    await p.goto(baseURL, { waitUntil: "load" });
    await p.waitForSelector("#authEmail", { timeout: 20000 });
    await p.fill("#authEmail", email);
    await p.keyboard.press("Enter");
    await p.waitForTimeout(4000);
    await p.click("text=Use a code instead").catch(() => {});
    await p.waitForSelector("#authCode", { timeout: 20000 });
    if (fs.existsSync(CODE)) fs.unlinkSync(CODE);
    console.log(`[setup] Waiting for the Clerk code: set WICHITA_CODE or write it to ${CODE}`);
    let code = process.env.WICHITA_CODE || null;
    for (let i = 0; i < 600 && !code; i++) {
      if (fs.existsSync(CODE)) code = fs.readFileSync(CODE, "utf8").trim();
      else await p.waitForTimeout(1000);
    }
    if (!code) throw new Error("No sign-in code received");
    await p.fill("#authCode", code);
    await p.keyboard.press("Enter");
    await p.waitForSelector("#appShell:not([hidden])", { timeout: 30000 });
    await ctx.storageState({ path: STATE });
    await ctx.close();
  } finally {
    await browser.close();
  }
}
