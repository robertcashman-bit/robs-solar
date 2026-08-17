import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("energy analytics redirects to finance overview", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/analytics");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
});
