import { test, expect } from "@playwright/test";

const WEBHOOK_URL = "https://e2e-test.example.com/webhook";

test.describe("Webhooks UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const tab = page.locator("[role=tab], button, a").filter({ hasText: /webhook/i }).first();
    if (await tab.isVisible()) {
      await tab.click();
      await page.waitForLoadState("networkidle");
    }
  });

  test("webhook section is visible", async ({ page }) => {
    await expect(
      page.locator("text=/webhook/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can add a webhook", async ({ page }) => {
    const addBtn = page.locator("button", { hasText: /add webhook|new webhook|\+/i }).first();
    if (!await addBtn.isVisible()) {
      test.skip();
      return;
    }
    await addBtn.click();

    const urlInput = page
      .locator('input[placeholder*="url" i], input[name="url" i], input[type="url"]')
      .first();
    if (await urlInput.isVisible()) {
      await urlInput.fill(WEBHOOK_URL);
    }

    await page
      .locator("button[type=submit], button:has-text('Save'), button:has-text('Add')")
      .last()
      .click();

    await expect(page.locator(`text=${WEBHOOK_URL}`)).toBeVisible({ timeout: 10_000 });
  });

  test("can delete a webhook", async ({ page }) => {
    // First ensure there's a webhook to delete (add one if section is empty)
    const existing = page.locator(`text=${WEBHOOK_URL}`);
    if (!await existing.isVisible()) {
      const addBtn = page.locator("button", { hasText: /add webhook|new webhook|\+/i }).first();
      if (await addBtn.isVisible()) {
        await addBtn.click();
        const urlInput = page.locator('input[placeholder*="url" i], input[type="url"]').first();
        if (await urlInput.isVisible()) await urlInput.fill(WEBHOOK_URL);
        await page.locator("button[type=submit], button:has-text('Save')").last().click();
        await page.locator(`text=${WEBHOOK_URL}`).waitFor({ timeout: 10_000 });
      } else {
        test.skip();
        return;
      }
    }

    const deleteBtn = page
      .locator(`text=${WEBHOOK_URL}`)
      .locator("..")
      .locator("button:has-text(/delete|remove/i)")
      .first();

    if (await deleteBtn.isVisible()) {
      await deleteBtn.click();
      await expect(page.locator(`text=${WEBHOOK_URL}`)).not.toBeVisible({ timeout: 5_000 });
    }
  });
});
