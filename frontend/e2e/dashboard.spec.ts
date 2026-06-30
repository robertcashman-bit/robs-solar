import { expect, test } from "@playwright/test";

import { loginAsAdmin, loginAsViewer } from "./helpers";

test("app boot and login shows dashboard metrics", async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByLabel("Savings control centre KPIs")).toBeVisible();
  await expect(page.getByLabel("Energy flow")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Today", exact: true })).toBeVisible();
  await expect(page.getByText("Simulated data")).toBeVisible();
});

test("viewer cannot access controls page", async ({ page }) => {
  await loginAsViewer(page);
  await page.goto("/controls");
  await expect(page.getByLabel("Energy flow")).toBeVisible({ timeout: 15000 });
});
