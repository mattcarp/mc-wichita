// Wichita live visual + consistency suite. Runs against the live site with ONE shared
// Clerk sign-in (global-setup.js saves .auth/state.json; every test reuses it).
//   cd tests/visual && npm i && npx playwright test
// Env: WICHITA_URL (default https://wichitawire.com), WICHITA_EMAIL, WICHITA_CODE (or write the
// emailed code to .auth/code.txt while setup waits), CHROME_PATH (optional system Chrome).
import { defineConfig } from "@playwright/test";
const launchOptions = process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {};
export default defineConfig({
  testDir: ".",
  testMatch: /.*\.spec\.js/,
  globalSetup: "./global-setup.js",
  timeout: 90_000,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.03, animations: "disabled", caret: "hide" } },
  snapshotPathTemplate: "{testDir}/baselines/{projectName}/{arg}{ext}",
  use: {
    baseURL: process.env.WICHITA_URL || "https://wichitawire.com",
    storageState: ".auth/state.json",
    launchOptions,
    timezoneId: "Europe/Malta",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    { name: "phone", use: { viewport: { width: 390, height: 844 }, hasTouch: true, deviceScaleFactor: 2 } },
  ],
});
