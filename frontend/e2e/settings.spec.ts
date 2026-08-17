import { expect, test } from "@playwright/test";

import { openFinanceSettings } from "./helpers";

test("settings page is finance-only", async ({ page }) => {
  await openFinanceSettings(page);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Energy / Solar" })).toHaveCount(0);
  await expect(page.getByText(/Sunsynk|Octopus Energy|Tesla|Energy savings/i)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "App shortcut" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Open Banking (TrueLayer)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lunch Flow" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Funding Circle" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "QuickFile" })).toBeVisible();
});
