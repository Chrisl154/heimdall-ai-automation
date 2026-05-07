import { test, expect } from "@playwright/test";

test.describe("Scheduler", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/schedule");
    await page.waitForLoadState("networkidle");
  });

  test("schedule page renders without error", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/schedule");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("renders schedule list or empty state", async ({ page }) => {
    await expect(
      page.locator("text=/schedule|cron|no scheduled/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can open add schedule dialog", async ({ page }) => {
    const addBtn = page
      .locator("button", { hasText: /add|new|create|schedule/i })
      .first();
    if (await addBtn.isVisible()) {
      await addBtn.click();
      await expect(
        page.locator("text=/cron|title|description/i").first()
      ).toBeVisible({ timeout: 5_000 });
    }
  });

  test("creates a scheduled task", async ({ page }) => {
    const addBtn = page
      .locator("button", { hasText: /add|new|create|schedule/i })
      .first();
    if (!await addBtn.isVisible()) {
      test.skip();
      return;
    }
    await addBtn.click();

    // Fill cron expression
    const cronInput = page
      .locator('input[placeholder*="cron" i], input[name="cron" i]')
      .first();
    if (await cronInput.isVisible()) {
      await cronInput.fill("0 9 * * 1");
    }

    // Fill title
    const titleInput = page
      .locator('input[placeholder*="title" i], input[name="title" i]')
      .first();
    if (await titleInput.isVisible()) {
      await titleInput.fill("E2E Weekly Report");
    }

    // Fill description
    const descInput = page.locator("textarea").first();
    if (await descInput.isVisible()) {
      await descInput.fill("Playwright e2e scheduled task");
    }

    await page.locator("button[type=submit], button:has-text('Save'), button:has-text('Create')").last().click();
    await expect(page.locator("text=E2E Weekly Report")).toBeVisible({ timeout: 10_000 });
  });
});
