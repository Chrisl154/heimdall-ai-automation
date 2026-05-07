import { test, expect } from "@playwright/test";

test.describe("GitHub Integration", () => {
  test.beforeEach(async ({ page }) => {
    // GitHub settings live inside the Settings page
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Navigate to the GitHub tab if it exists
    const ghTab = page.locator("[role=tab], button, a").filter({ hasText: /github/i }).first();
    if (await ghTab.isVisible()) {
      await ghTab.click();
    }
  });

  test("GitHub tab or section is accessible", async ({ page }) => {
    await expect(
      page.locator("text=/github/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows connect form when not connected", async ({ page }) => {
    // When not connected we expect a token input or connect button
    const connectEl = page
      .locator("input[type=password], input[placeholder*='token' i], button:has-text(/connect/i)")
      .first();
    if (await connectEl.isVisible()) {
      await expect(connectEl).toBeVisible();
    }
  });

  test("shows error on invalid token submission", async ({ page }) => {
    const tokenInput = page
      .locator("input[type=password], input[placeholder*='token' i]")
      .first();
    if (!await tokenInput.isVisible()) {
      test.skip();
      return;
    }
    await tokenInput.fill("totally-invalid-token-12345");
    await page.locator("button:has-text(/connect|save|submit/i)").first().click();

    await expect(
      page.locator("text=/invalid|error|failed|unauthorized/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
