import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./playwright",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    viewport: { width: 420, height: 720 },
    colorScheme: "dark",
  },
  webServer: {
    command: "python3 -m http.server 8765",
    cwd: "..",
    port: 8765,
    reuseExistingServer: true,
  },
});
