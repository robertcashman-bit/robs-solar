import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("restore flow in simulator mode", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).toBeVisible();

  await page.getByLabel("Export limit (W)").fill("2000");
  await page.getByRole("button", { name: "Review change" }).first().click();
  await page.getByRole("button", { name: "Confirm write" }).click();
  await expect(page.getByText(/Export limit set to 2000 W/i)).toBeVisible();

  await page.getByLabel("Export limit (W)").fill("3000");
  await page.getByRole("button", { name: "Review change" }).first().click();
  await page.getByRole("button", { name: "Confirm write" }).click();
  await expect(page.getByText(/Export limit set to 3000 W/i)).toBeVisible();

  await page.getByRole("button", { name: "Restore last known good" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Restore", exact: true }).click();
  await expect(page.getByText(/Last known good configuration restored/i)).toBeVisible();

  await gotoWhenAuthed(page, "/audit");
  await expect(page.getByRole("cell", { name: "restore_last_known_good" }).first()).toBeVisible();
});
