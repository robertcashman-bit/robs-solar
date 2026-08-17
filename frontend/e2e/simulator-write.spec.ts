import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("inverter write pages are removed", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Controls" })).toHaveCount(0);
  await expect(page.getByLabel("Export limit (W)")).toHaveCount(0);
});
