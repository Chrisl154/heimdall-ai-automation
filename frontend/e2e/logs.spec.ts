import { test, expect } from "@playwright/test";

test.describe("Logs", () => {
  test("loads without uncaught JS errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/logs");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("event log section is present", async ({ page }) => {
    await page.goto("/logs");
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("text=/event|log|pipeline/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("app log section is present", async ({ page }) => {
    await page.goto("/logs");
    await page.waitForLoadState("networkidle");
    // Should render a textarea, pre, or scrollable container for raw log output
    await expect(
      page.locator("textarea, pre, [class*=log], [class*=terminal]").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("log table has column headers", async ({ page }) => {
    await page.goto("/logs");
    await page.waitForLoadState("networkidle");
    await expect(
      page.locator("th, [role=columnheader]").first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
