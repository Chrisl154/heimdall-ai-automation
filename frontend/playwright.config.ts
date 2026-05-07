import { defineConfig, devices } from "@playwright/test";

/**
 * Heimdall end-to-end test configuration.
 *
 * Prerequisites:
 *   - Backend running on http://localhost:8000
 *   - HEIMDALL_API_TOKEN set (or empty for dev mode)
 *   - Frontend dev server auto-started by this config
 *
 * Run:  npm run test:e2e
 * UI:   npm run test:e2e -- --ui
 */

const TOKEN = process.env.HEIMDALL_API_TOKEN ?? "";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,       // SSE tests share backend state — keep sequential
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Pre-seed localStorage with the API token so tests start authenticated
    storageState: {
      cookies: [],
      origins: [
        {
          origin: "http://localhost:3000",
          localStorage: TOKEN
            ? [{ name: "heimdall_token", value: TOKEN }]
            : [],
        },
      ],
    },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
