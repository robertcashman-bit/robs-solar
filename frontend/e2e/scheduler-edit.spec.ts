import { expect, test } from "@playwright/test";

import { loginAsViewer, gotoWhenAuthed } from "./helpers";

test("energy scheduler redirects to finance overview", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/scheduler");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Time-of-use scheduler" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});

test.describe("viewer access", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("viewer energy scheduler also redirects home", async ({ page }) => {
    await loginAsViewer(page);
    await page.goto("/energy/scheduler");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Edit schedule" })).toHaveCount(0);
  });
});
