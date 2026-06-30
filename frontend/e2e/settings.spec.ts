import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test("settings page shows live writes disabled", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Safety & configuration" })).toBeVisible();
  await expect(page.getByText(/Live writes disabled/i)).toBeVisible();
});
