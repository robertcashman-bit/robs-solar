import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("settings page shows live writes disabled", async ({ page }) => {
  await gotoWhenAuthed(page, "/settings");
  await expect(page.getByRole("heading", { name: "Safety & configuration" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText(/Live writes disabled/i)).toBeVisible({ timeout: 20_000 });
});
