import { defineConfig } from "@playwright/test";
import { browserEvidencePath } from "./tests/browser/evidence";

export default defineConfig({
  testDir: "./tests/browser",
  timeout: 45_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 2,
  retries: 0,
  ...(process.env.EARTHMIND_EVIDENCE_DIR
    ? { outputDir: browserEvidencePath("test-results") }
    : {}),
  reporter: [
    ["list"],
    [
      "json",
      { outputFile: browserEvidencePath("playwright-results.json") },
    ],
  ],
  use: {
    baseURL: process.env.WEB_BASE_URL ?? "http://127.0.0.1:3000",
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "tablet", use: { viewport: { width: 820, height: 1180 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
