import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("inverter settings page is display-only with no export write form", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page.getByRole("heading", { name: "Inverter settings" })).toBeVisible();
  await expect(page.getByText(/Display only/i)).toBeVisible();
  await expect(page.getByLabel("Export limit (W)")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirm write" })).toHaveCount(0);
});
