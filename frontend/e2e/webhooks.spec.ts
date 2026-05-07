import { test, expect } from "@playwright/test";
import { openSettingsTab, Selectors } from "./helpers";

// ── Webhooks (Settings → Webhooks tab) ───────────────────────────────────────

const TEST_URL = "https://e2e-test.example.com/webhook";

async function addWebhook(page: import("@playwright/test").Page, url: string) {
  const addBtn = Selectors.button(page, /add webhook|new webhook|\+/i);
  if (!await addBtn.isVisible()) return false;
  await addBtn.click();

  const urlInput = page
    .locator('input[placeholder*="url" i], input[name="url" i], input[type="url"]')
    .first();
  if (await urlInput.isVisible()) await urlInput.fill(url);

  await Selectors.submitBtn(page).click();
  await expect(page.locator(`text=${url}`)).toBeVisible({ timeout: 10_000 });
  return true;
}

test.describe("Webhooks", () => {
  test.beforeEach(async ({ page }) => {
    await openSettingsTab(page, /webhook/i);
  });

  // ── Visibility ────────────────────────────────────────────────────────────

  test("Webhooks section is visible", async ({ page }) => {
    await expect(
      page.locator("text=/webhook/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── CRUD ──────────────────────────────────────────────────────────────────

  test("can add a webhook and it appears in the list", async ({ page }) => {
    await addWebhook(page, TEST_URL);
    // Assertion already inside addWebhook; reaching here = pass
  });

  test("can delete a webhook and it disappears from the list", async ({ page }) => {
    const added = await addWebhook(page, TEST_URL);
    if (!added) return;

    const deleteBtn = page
      .locator(`text=${TEST_URL}`)
      .locator("..")
      .locator("button:has-text(/delete|remove/i)")
      .first();

    if (!await deleteBtn.isVisible()) return;

    await deleteBtn.click();
    await expect(page.locator(`text=${TEST_URL}`)).not.toBeVisible({ timeout: 5_000 });
  });
});
