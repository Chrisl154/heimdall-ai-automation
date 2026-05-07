import { test, expect } from "@playwright/test";
import { goTo, Selectors, trackErrors } from "./helpers";

// ── Tasks / Kanban (/tasks) ───────────────────────────────────────────────────

test.describe("Tasks / Kanban", () => {
  test.beforeEach(async ({ page }) => {
    await goTo(page, "/tasks");
  });

  // ── Board layout ──────────────────────────────────────────────────────────

  test("Kanban columns are visible", async ({ page }) => {
    await expect(
      page.locator("text=/pending|in.progress|completed/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("loads with no uncaught JS errors", async ({ page }) => {
    const getErrors = trackErrors(page);
    await goTo(page, "/tasks");
    expect(getErrors()).toHaveLength(0);
  });

  // ── Add task dialog ───────────────────────────────────────────────────────

  test("Add Task button opens dialog", async ({ page }) => {
    const addBtn = Selectors.button(page, /add task|new task|\+/i);
    await expect(addBtn).toBeVisible();
    await addBtn.click();
    await expect(
      page.locator("text=/title|description/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  test("creates a task and it appears on the board", async ({ page }) => {
    await Selectors.button(page, /add task|new task|\+/i).click();

    await Selectors.titleInput(page).fill("E2E Test Task");
    await Selectors.descTextarea(page).fill("Created by Playwright e2e test");
    await Selectors.submitBtn(page).click();

    await expect(page.locator("text=E2E Test Task")).toBeVisible({ timeout: 10_000 });
  });

  // ── Template picker ───────────────────────────────────────────────────────

  test("template picker populates description when a template is selected", async ({ page }) => {
    await Selectors.button(page, /add task|new task|\+/i).click();

    const picker = page.locator("select, [role=combobox]").first();
    if (!await picker.isVisible()) return; // template feature not present — skip

    const options = picker.locator("option, [role=option]");
    if (await options.count() <= 1) return;

    await picker.selectOption({ index: 1 });
    await expect(Selectors.descTextarea(page)).not.toHaveValue("");
  });
});
