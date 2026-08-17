import { expect, test } from "@playwright/test";

import { loginAsAdmin, loginAsViewer } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("app boot and login shows finance overview, not energy", async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await page.goto("/energy");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Energy" }),
  ).toHaveCount(0);
});

test("viewer cannot open energy controls", async ({ page }) => {
  await loginAsViewer(page);
  await page.goto("/energy/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).not.toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});
