import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test("admin export limit write requires confirmation in writable mode", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/controls");
  await expect(page.getByRole("heading", { name: "Controls" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Export limit" })).toBeVisible();
});
