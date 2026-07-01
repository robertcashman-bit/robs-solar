import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test("admin can update tariff on settings page", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/settings");
  await expect(page.getByText("Electricity tariff")).toBeVisible();
  await page.getByRole("spinbutton", { name: "Import rate (per kWh)", exact: true }).fill("0.30");
  await page.getByRole("spinbutton", { name: "Export rate (per kWh)" }).fill("0.10");
  await page.getByRole("button", { name: "Review change" }).click();
  await page.getByRole("button", { name: "Confirm write" }).click();
  await expect(page.getByText(/Tariff updated/i)).toBeVisible();
});
