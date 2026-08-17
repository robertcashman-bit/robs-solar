import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("energy controls redirect to finance overview", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Controls" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});
