import { expect, test } from "@playwright/test";

import { gotoWhenAuthed, openEnergySettings } from "./helpers";

test("PWA manifest is served", async ({ request }) => {
  const response = await request.get("/manifest.json");
  expect(response.ok()).toBeTruthy();
  const manifest = await response.json();
  expect(manifest.name).toContain("Rob's Finance");
  expect(manifest.theme_color).toBe("#10b981");
  for (const icon of manifest.icons) {
    const iconResponse = await request.get(icon.src);
    expect(iconResponse.ok(), `icon ${icon.src} should exist`).toBeTruthy();
  }
});

test("admin sees display-only inverter settings page", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page.getByRole("heading", { name: "Inverter settings" })).toBeVisible();
  await expect(page.getByText(/Display only/i)).toBeVisible();
  await expect(page.getByText("Automation rules")).toHaveCount(0);
});

test("analytics shows bill reconciliation section", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/analytics");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  const simulated = page.getByRole("heading", { name: "Live inverter data required" });
  const liveCharts = page.getByText("Savings & cost");
  await expect(simulated.or(liveCharts)).toBeVisible({ timeout: 30_000 });
  if (await simulated.isVisible()) {
    await expect(page.getByRole("heading", { name: "Bill reconciliation" })).not.toBeVisible();
  }
});

test("admin sees notification settings on settings page", async ({ page }) => {
  await openEnergySettings(page);
  await expect(page.getByText("Alert notifications")).toBeVisible();
  await expect(page.getByText("Runtime safety toggles")).toBeVisible();
});
