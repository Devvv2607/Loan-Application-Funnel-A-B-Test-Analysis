import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  workers: 2,
  reporter: "list",
  use: { baseURL: "http://localhost:4173", browserName: "chromium" },
  webServer: { command: "node scripts/serve.mjs", url: "http://localhost:4173", reuseExistingServer: true },
});
