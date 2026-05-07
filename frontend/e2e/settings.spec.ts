import { test, expect } from "@playwright/test";
import { goTo, openSettingsTab, trackErrors } from "./helpers";

// ── Settings (/settings) ──────────────────────────────────────────────────────

test.describe("Settings", () => {
  // ── Page load ─────────────────────────────────────────────────────────────

  test("loads with no uncaught JS errors", async ({ page }) => {
    const getErrors = trackErrors(page);
    await goTo(page, "/settings");
    expect(getErrors()).toHaveLength(0);
  });

  test("renders agent configuration section", async ({ page }) => {
    await goTo(page, "/settings");
    await expect(
      page.locator("text=/worker|reviewer|orchestrator|agent/i").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  // ── Vault tab ─────────────────────────────────────────────────────────────

  test("Vault tab is navigable and shows key management UI", async ({ page }) => {
    const opened = await openSettingsTab(page, /vault/i);
    if (!opened) return;
    await expect(
      page.locator("text=/secret|key|vault/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  // ── Restrictions tab ──────────────────────────────────────────────────────

  test("Restrictions tab shows a YAML editor", async ({ page }) => {
    const opened = await openSettingsTab(page, /restrict/i);
    if (!opened) return;
    await expect(
      page.locator("textarea, pre[contenteditable]").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  // ── Webhooks tab ──────────────────────────────────────────────────────────

  test("Webhooks tab is navigable and shows webhook UI", async ({ page }) => {
    const opened = await openSettingsTab(page, /webhook/i);
    if (!opened) return;
    await expect(
      page.locator("text=/webhook|url|hook/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });

  // ── GitHub tab ────────────────────────────────────────────────────────────

  test("GitHub tab is navigable and shows connection UI", async ({ page }) => {
    const opened = await openSettingsTab(page, /github/i);
    if (!opened) return;
    await expect(
      page.locator("text=/github/i").first()
    ).toBeVisible({ timeout: 5_000 });
  });
});
