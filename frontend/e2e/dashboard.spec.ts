import { test, expect } from "@playwright/test";
import { goTo, trackErrors } from "./helpers";

// ── Dashboard (/) ─────────────────────────────────────────────────────────────

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await goTo(page, "/");
  });

  // ── Layout ────────────────────────────────────────────────────────────────

  test("PM control section is visible", async ({ page }) => {
    await expect(
      page.locator("text=/pm|pipeline|agent|start|stop/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("task summary section is visible", async ({ page }) => {
    await expect(
      page.locator("text=/task|pending|completed|failed/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("Models Talking panel is present", async ({ page }) => {
    await expect(
      page.locator("text=/talking|conversation|agent|live/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── Reliability ───────────────────────────────────────────────────────────

  test("loads with no uncaught JS errors", async ({ page }) => {
    const getErrors = trackErrors(page);
    await goTo(page, "/");
    expect(getErrors()).toHaveLength(0);
  });
});
