import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("energy scheduler auto-align is removed", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/scheduler");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Time-of-use scheduler" })).toHaveCount(0);
});
