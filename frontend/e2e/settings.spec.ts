import { expect, test } from "@playwright/test";

import { openEnergySettings } from "./helpers";

test("settings page shows live writes status", async ({ page }) => {
  await openEnergySettings(page);
  await expect(page.getByRole("heading", { name: "Safety & configuration" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/Live writes disabled/i).or(page.getByText("Live writes on")),
  ).toBeVisible({ timeout: 20_000 });
});
