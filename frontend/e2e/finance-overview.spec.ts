import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("finance overview is default landing", async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("region", { name: "What's left" })).toBeVisible();
  await expect(page.getByRole("region", { name: "You" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Defence Legal" })).toBeVisible();
  await expect(page.getByText("What you own").first()).toBeVisible();
  await expect(page.getByText(/net worth/i)).toHaveCount(0);
});

test("energy dashboard is removed", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/energy");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByLabel("Live power now")).toHaveCount(0);
});
