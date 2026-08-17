import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("inverter restore flow is removed with energy controls", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Controls" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Restore last known good" })).toHaveCount(0);
});
