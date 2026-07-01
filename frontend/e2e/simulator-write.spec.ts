import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("simulator export limit write appears in audit log", async ({ page }) => {
  await gotoWhenAuthed(page, "/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).toBeVisible();

  await page.getByLabel("Export limit (W)").fill("2500");
  await page.getByRole("button", { name: "Review change" }).first().click();
  await page.getByRole("button", { name: "Confirm write" }).click();
  await expect(page.getByText(/Export limit set to 2500 W/i)).toBeVisible();

  await gotoWhenAuthed(page, "/audit");
  await expect(page.getByRole("cell", { name: "set_export_limit" }).first()).toBeVisible();
});
