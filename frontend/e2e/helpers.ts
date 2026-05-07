/**
 * Shared helpers and page-object utilities for Heimdall e2e tests.
 */
import { type Page, expect } from "@playwright/test";

// ── Navigation ────────────────────────────────────────────────────────────────

export async function goTo(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
}

// ── Console error guard ───────────────────────────────────────────────────────

export function trackErrors(page: Page): () => string[] {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));
  return () => errors;
}

// ── Shared locators ───────────────────────────────────────────────────────────

export const Selectors = {
  /** First button whose text matches the regex */
  button: (page: Page, text: RegExp) =>
    page.locator("button", { hasText: text }).first(),

  /** First tab/link whose text matches the regex */
  tab: (page: Page, text: RegExp) =>
    page.locator("[role=tab], button, a").filter({ hasText: text }).first(),

  /** Title input in a dialog/form */
  titleInput: (page: Page) =>
    page.locator('input[placeholder*="title" i], input[name="title" i]').first(),

  /** Description textarea in a dialog/form */
  descTextarea: (page: Page) =>
    page.locator('textarea[placeholder*="description" i], textarea[name="description" i]').first(),

  /** Submit button in the currently open dialog/form */
  submitBtn: (page: Page) =>
    page.locator("button[type=submit], button:has-text('Save'), button:has-text('Create'), button:has-text('Add')").last(),
};

// ── Common assertions ─────────────────────────────────────────────────────────

export async function expectTextVisible(page: Page, pattern: RegExp, timeout = 10_000) {
  await expect(page.locator(`text=${pattern}`).or(page.locator("body")).filter({ hasText: pattern }).first()).toBeVisible({ timeout });
}

export async function expectNoJsErrors(page: Page, path: string) {
  const getErrors = trackErrors(page);
  await goTo(page, path);
  expect(getErrors()).toHaveLength(0);
}

// ── Settings tab navigation ───────────────────────────────────────────────────

export async function openSettingsTab(page: Page, tabName: RegExp): Promise<boolean> {
  await goTo(page, "/settings");
  const tab = Selectors.tab(page, tabName);
  if (!await tab.isVisible()) return false;
  await tab.click();
  await page.waitForLoadState("networkidle");
  return true;
}
