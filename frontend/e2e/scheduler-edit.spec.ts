import { expect, test } from "@playwright/test";

import { loginAsViewer, gotoWhenAuthed } from "./helpers";

test("scheduler is display-only and shows strategy previews", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/scheduler");

  await expect(page.getByRole("heading", { name: "Time-of-use schedule" })).toBeVisible();
  await expect(page.getByText(/Display only/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Strategy previews" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Edit schedule" })).toHaveCount(0);
  await expect(page.getByText(/Confirm & apply/i)).toHaveCount(0);
});

test.describe("viewer access", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("viewer sees the read-only scheduler without write controls", async ({ page }) => {
    await loginAsViewer(page);
    await page.goto("/energy/scheduler");
    await expect(page.getByRole("heading", { name: "Time-of-use schedule" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "Edit schedule" })).toHaveCount(0);
  });
});
