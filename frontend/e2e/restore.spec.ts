import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("inverter settings page has no restore write flow", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page.getByRole("heading", { name: "Inverter settings" })).toBeVisible();
  await expect(page.getByText(/Display only/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Restore last known good" })).toHaveCount(0);
  await expect(page.getByLabel("Export limit (W)")).toHaveCount(0);
});
