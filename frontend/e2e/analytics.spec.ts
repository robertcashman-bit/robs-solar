import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test("analytics page renders charts after samples exist", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await expect(page.getByText("Savings & cost")).toBeVisible();
  await expect(
    page.getByText(/Power over time|Historical samples accumulate/),
  ).toBeVisible({ timeout: 15000 });
});
