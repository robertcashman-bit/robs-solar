import { expect, test } from "@playwright/test";

import { loginAsAdmin, loginAsViewer } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

test("app boot and login shows dashboard metrics", async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page.getByRole("heading", { name: "Live inverter data required" })).toBeVisible();
  await expect(page.getByLabel("Live power now")).not.toBeVisible();
});

test("viewer cannot access controls page", async ({ page }) => {
  await loginAsViewer(page);
  await page.goto("/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).toBeVisible({ timeout: 15_000 });
});
