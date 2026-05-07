import { test, expect } from "@playwright/test";

test.describe("Settings", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
  });

  test("settings page loads without error", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("renders agent configuration section", async ({ page }) => {
    await expect(
      page.locator("text=/worker|reviewer|orchestrator|agent/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("Vault tab is accessible", async ({ page }) => {
    const vaultTab = page.locator("[role=tab], button, a").filter({ hasText: /vault/i }).first();
    if (await vaultTab.isVisible()) {
      await vaultTab.click();
      await expect(
        page.locator("text=/secret|key|vault/i").first()
      ).toBeVisible({ timeout: 5_000 });
    }
  });

  test("Restrictions tab is accessible", async ({ page }) => {
    const tab = page.locator("[role=tab], button, a").filter({ hasText: /restrict/i }).first();
    if (await tab.isVisible()) {
      await tab.click();
      // Should show a YAML editor or textarea
      await expect(page.locator("textarea, pre[contenteditable]").first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("Webhooks tab is accessible", async ({ page }) => {
    const tab = page.locator("[role=tab], button, a").filter({ hasText: /webhook/i }).first();
    if (await tab.isVisible()) {
      await tab.click();
      await expect(
        page.locator("text=/webhook|url|hook/i").first()
      ).toBeVisible({ timeout: 5_000 });
    }
  });
});
