import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("finance overview is default landing", async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Totals by scope" })).toBeVisible();
});

test("energy dashboard is removed", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/energy");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByLabel("Live power now")).toHaveCount(0);
});
