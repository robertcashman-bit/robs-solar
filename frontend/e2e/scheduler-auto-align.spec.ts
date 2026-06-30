import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test("admin sees auto-align panel on scheduler page", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/scheduler");
  await expect(page.getByRole("heading", { name: "Time-of-use scheduler" })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Auto-align battery to IOG windows" }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole("button", { name: /Enable auto-align/i })).toBeVisible();
});
