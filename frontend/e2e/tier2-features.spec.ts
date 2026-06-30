import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test("PWA manifest is served", async ({ request }) => {
  const response = await request.get("/manifest.json");
  expect(response.ok()).toBeTruthy();
  const manifest = await response.json();
  expect(manifest.name).toContain("Rob's Solar");
  expect(manifest.theme_color).toBe("#f59e0b");
});

test("admin can view automation rules on controls page", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/controls");
  await expect(page.getByText("Automation rules")).toBeVisible();
});

test("analytics shows bill reconciliation section", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/analytics");
  await expect(page.getByText("Bill reconciliation")).toBeVisible();
});

test("admin sees notification settings on settings page", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/settings");
  await expect(page.getByText("Alert notifications")).toBeVisible();
  await expect(page.getByText("Runtime safety toggles")).toBeVisible();
});
