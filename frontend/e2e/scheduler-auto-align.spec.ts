import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("auto-align write panel is not shown on the display-only scheduler", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/scheduler");
  await expect(page.getByRole("heading", { name: "Time-of-use schedule" })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Auto-align battery to IOG windows" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Enable auto-align/i })).toHaveCount(0);
});
