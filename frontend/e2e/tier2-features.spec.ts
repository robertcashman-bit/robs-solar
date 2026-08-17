import { expect, test } from "@playwright/test";

import { gotoWhenAuthed, openFinanceSettings } from "./helpers";

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

test("energy routes redirect to the finance overview", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Energy" }),
  ).toHaveCount(0);
});

test("leftover energy pages redirect home", async ({ page }) => {
  for (const path of ["/alerts", "/audit", "/energy/analytics", "/energy/controls"]) {
    await gotoWhenAuthed(page, path);
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  }
});

test("settings has no energy or Sunsynk controls", async ({ page }) => {
  await openFinanceSettings(page);
  await expect(page.getByText("Alert notifications")).toHaveCount(0);
  await expect(page.getByText(/Sunsynk/i)).toHaveCount(0);
});
