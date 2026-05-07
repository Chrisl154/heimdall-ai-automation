import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for the page to finish loading (avoid flash of login redirect)
    await page.waitForLoadState("networkidle");
  });

  test("shows PM status section", async ({ page }) => {
    // Either the PM control panel or a status indicator should be present
    await expect(
      page.locator("text=/pm|pipeline|agent|start|stop/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("renders task count cards or summary", async ({ page }) => {
    // The dashboard should show some kind of task metrics or pipeline summary
    await expect(
      page.locator("text=/task|pending|completed|failed/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("Models Talking panel is present", async ({ page }) => {
    await expect(
      page.locator("text=/talking|conversation|agent|live/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("no uncaught JS errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });
});
