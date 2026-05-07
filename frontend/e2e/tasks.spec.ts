import { test, expect } from "@playwright/test";

test.describe("Tasks / Kanban", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tasks");
    await page.waitForLoadState("networkidle");
  });

  test("Kanban board renders column headers", async ({ page }) => {
    await expect(
      page.locator("text=/pending|in.progress|completed/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can open the Add Task dialog", async ({ page }) => {
    const addBtn = page.locator("button", { hasText: /add task|new task|\+/i }).first();
    await expect(addBtn).toBeVisible();
    await addBtn.click();
    await expect(page.locator("text=/title|description/i").first()).toBeVisible();
  });

  test("creates a task and it appears on the board", async ({ page }) => {
    const addBtn = page.locator("button", { hasText: /add task|new task|\+/i }).first();
    await addBtn.click();

    const titleInput = page
      .locator('input[placeholder*="title" i], input[name="title" i]')
      .first();
    await titleInput.fill("E2E Test Task");

    const descInput = page
      .locator('textarea[placeholder*="description" i], textarea[name="description" i]')
      .first();
    await descInput.fill("Created by Playwright e2e test");

    await page.locator("button[type=submit], button:has-text('Create'), button:has-text('Add')").last().click();

    await expect(page.locator("text=E2E Test Task")).toBeVisible({ timeout: 10_000 });
  });

  test("template picker populates description when selected", async ({ page }) => {
    const addBtn = page.locator("button", { hasText: /add task|new task|\+/i }).first();
    await addBtn.click();

    // If a template selector exists, pick the first option
    const templatePicker = page.locator("select, [role=combobox]").first();
    if (await templatePicker.isVisible()) {
      const options = templatePicker.locator("option, [role=option]");
      const count = await options.count();
      if (count > 1) {
        await templatePicker.selectOption({ index: 1 });
        const descInput = page.locator("textarea").first();
        await expect(descInput).not.toHaveValue("");
      }
    }
  });
});
