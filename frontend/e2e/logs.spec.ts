import { test, expect } from "@playwright/test";
import { goTo, trackErrors } from "./helpers";

// ── Logs (/logs) ──────────────────────────────────────────────────────────────

test.describe("Logs", () => {
  test.beforeEach(async ({ page }) => {
    await goTo(page, "/logs");
  });

  // ── Page load ─────────────────────────────────────────────────────────────

  test("loads with no uncaught JS errors", async ({ page }) => {
    const getErrors = trackErrors(page);
    await goTo(page, "/logs");
    expect(getErrors()).toHaveLength(0);
  });

  // ── Event log section ─────────────────────────────────────────────────────

  test("event log section is present", async ({ page }) => {
    await expect(
      page.locator("text=/event|log|pipeline/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("event log table has column headers", async ({ page }) => {
    await expect(
      page.locator("th, [role=columnheader]").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── App log section ───────────────────────────────────────────────────────

  test("app log output area is rendered", async ({ page }) => {
    // Raw log output is shown in a textarea, pre, or scrollable container
    await expect(
      page.locator("textarea, pre, [class*=log], [class*=terminal]").first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
