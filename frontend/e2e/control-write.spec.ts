import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("inverter settings page has no write controls", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page.getByRole("heading", { name: "Inverter settings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Export limit" })).toHaveCount(0);
  await expect(page.getByText(/Display only/i)).toBeVisible();
});
