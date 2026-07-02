import { expect, test } from "@playwright/test";

import { expectEnergyDashboard, loginAsAdmin, loginAsViewer } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("app boot and login shows energy dashboard", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/energy");
  await expectEnergyDashboard(page);
  const simulated = page.getByRole("heading", { name: "Live inverter data required" });
  if (await simulated.isVisible()) {
    await expect(page.getByLabel("Live power now")).not.toBeVisible();
  }
});

test("viewer cannot access controls page", async ({ page }) => {
  await loginAsViewer(page);
  await page.goto("/energy/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).not.toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});
