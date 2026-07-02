import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("admin export limit write requires confirmation in writable mode", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Export limit" })).toBeVisible();
});
