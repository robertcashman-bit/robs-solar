import { expect, test } from "@playwright/test";

import { loginAsViewer, gotoWhenAuthed } from "./helpers";

test("admin can edit a TOU band and write it to the inverter", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/scheduler");

  await expect(page.getByRole("heading", { name: "Time-of-use scheduler" })).toBeVisible();

  // Simulator serves a writable schedule, so the editor is shown to admins.
  const editor = page.getByRole("region", { name: "Edit inverter schedule" });
  await expect(editor.getByRole("heading", { name: "Edit schedule" })).toBeVisible({
    timeout: 15000,
  });

  await editor.getByLabel("Band 2 target SOC").fill("55");
  await editor.getByRole("button", { name: /Review .* write to inverter/i }).click();

  // Confirmation dialog -> write.
  await page.getByRole("button", { name: "Write to inverter", exact: true }).click();

  // The page raises a toast on a successful audited write.
  await expect(page.getByText(/Schedule written \(audit/i)).toBeVisible({
    timeout: 15000,
  });
});

test.describe("viewer access", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("viewer does not see the schedule editor", async ({ page }) => {
    await loginAsViewer(page);
    await page.goto("/energy/scheduler");
    await expect(page.getByRole("heading", { name: "Time-of-use scheduler" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "Edit schedule" })).toHaveCount(0);
  });
});
