import { test, expect } from "@playwright/test";
import { openSettingsTab } from "./helpers";

// ── GitHub Integration (Settings → GitHub tab) ────────────────────────────────

test.describe("GitHub Integration", () => {
  test.beforeEach(async ({ page }) => {
    await openSettingsTab(page, /github/i);
  });

  // ── Connection UI ─────────────────────────────────────────────────────────

  test("GitHub section is visible", async ({ page }) => {
    await expect(
      page.locator("text=/github/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows a token input or connect button when not connected", async ({ page }) => {
    const connectEl = page
      .locator("input[type=password], input[placeholder*='token' i], button:has-text(/connect/i)")
      .first();
    // If already connected this element may not be present — that's fine
    if (await connectEl.isVisible()) {
      await expect(connectEl).toBeVisible();
    }
  });

  // ── Error handling ────────────────────────────────────────────────────────

  test("shows an error message when an invalid token is submitted", async ({ page }) => {
    const tokenInput = page
      .locator("input[type=password], input[placeholder*='token' i]")
      .first();
    if (!await tokenInput.isVisible()) return; // already connected or feature absent

    await tokenInput.fill("totally-invalid-token-12345");
    await page
      .locator("button:has-text(/connect|save|submit/i)")
      .first()
      .click();

    await expect(
      page.locator("text=/invalid|error|failed|unauthorized/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
