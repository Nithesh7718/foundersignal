import { defineConfig, devices } from "@playwright/test";
import path from "path";

// Ensure custom browser path is set
process.env.PLAYWRIGHT_BROWSERS_PATH =
  process.env.PLAYWRIGHT_BROWSERS_PATH ||
  "/mnt/4B2725090A15B9D5/.cache/ms-playwright";

const TEST_RESULTS_DIR = path.resolve(__dirname, "../test-results");

export default defineConfig({
  testDir: "./tests",
  outputDir: path.join(TEST_RESULTS_DIR, "traces"),
  timeout: 30000,
  expect: {
    timeout: 7000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1, // Sequential execution for predictable state & test data
  reporter: [
    ["list"],
    ["html", { outputFolder: path.join(TEST_RESULTS_DIR, "html-report"), open: "never" }],
    ["json", { outputFile: path.join(TEST_RESULTS_DIR, "test-report.json") }],
  ],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
});
