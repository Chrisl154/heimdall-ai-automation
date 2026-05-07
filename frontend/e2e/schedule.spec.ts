import { test, expect } from "@playwright/test";
import { goTo, Selectors, trackErrors } from "./helpers";

// ── Scheduler (/schedule) ─────────────────────────────────────────────────────

test.describe("Scheduler", () => {
  test.beforeEach(async ({ page }) => {
    await goTo(page, "/schedule");
  });

  // ── Page load ─────────────────────────────────────────────────────────────

  test("loads with no uncaught JS errors", async ({ page }) => {
    const getErrors = trackErrors(page);
    await goTo(page, "/schedule");
    expect(getErrors()).toHaveLength(0);
  });

  test("renders schedule list or empty state", async ({ page }) => {
    await expect(
      page.locator("text=/schedule|cron|no scheduled/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── Add schedule dialog ───────────────────────────────────────────────────

  test("Add Schedule button opens dialog", async ({ page }) => {
    const addBtn = Selectors.button(page, /add|new|create|schedule/i);
    if (!await addBtn.isVisible()) return;
    await addBtn.click();
    await expect(
      page.locator("text=/cron|title|description/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("creates a scheduled task that appears in the list", async ({ page }) => {
    const addBtn = Selectors.button(page, /add|new|create|schedule/i);
    if (!await addBtn.isVisible()) return;
    await addBtn.click();

    // Fill cron expression
    const cronInput = page
      .locator('input[placeholder*="cron" i], input[name="cron" i]')
      .first();
    if (await cronInput.isVisible()) await cronInput.fill("0 9 * * 1");

    await Selectors.titleInput(page).fill("E2E Weekly Report");
    await Selectors.descTextarea(page).fill("Playwright e2e scheduled task");
    await Selectors.submitBtn(page).click();

    await expect(page.locator("text=E2E Weekly Report")).toBeVisible({ timeout: 10_000 });
  });
});
