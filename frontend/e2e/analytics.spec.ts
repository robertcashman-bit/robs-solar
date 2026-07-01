import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("analytics page renders charts after samples exist", async ({ page }) => {
  await gotoWhenAuthed(page, "/analytics");
  await expect(page.getByRole("heading", { name: "Live inverter data required" })).toBeVisible();
  await expect(page.getByText("Savings & cost")).not.toBeVisible();
});
