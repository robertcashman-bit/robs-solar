import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("finance overview is default landing", async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Balances")).toBeVisible();
});

test("energy dashboard accessible at /energy", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/energy");
  await expect(
    page.getByRole("heading", { name: "Live inverter data required" }).or(
      page.getByLabel("Live power now"),
    ),
  ).toBeVisible({ timeout: 15_000 });
});
