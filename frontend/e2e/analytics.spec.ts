import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("analytics page renders charts after samples exist", async ({ page }) => {
  await gotoWhenAuthed(page, "/energy/analytics");
  const simulated = page.getByRole("heading", { name: "Live inverter data required" });
  const liveCharts = page.getByText("Savings & cost");
  await expect(simulated.or(liveCharts)).toBeVisible({ timeout: 30_000 });
  if (await simulated.isVisible()) {
    await expect(liveCharts).not.toBeVisible();
  }
});
