import { defineConfig } from "@playwright/test";
// DOM snapshot tracing retains inspected nodes; functional tests retain traces separately.
export default defineConfig({
  testDir: "./tests/performance", testMatch: "**/*.performance.ts", timeout: 180_000, workers: 1, retries: 0,
  reporter: [["list"],["json",{outputFile:"../../docs/evidence/recovery/performance-results.json"}]],
  use: { baseURL: process.env.WEB_BASE_URL ?? "http://127.0.0.1:3000", browserName:"chromium", viewport:{width:1440,height:1000}, trace:"off" },
});
