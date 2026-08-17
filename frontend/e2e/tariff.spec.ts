import { expect, test } from "@playwright/test";

import { openFinanceSettings } from "./helpers";

test("energy tariff settings are not shown", async ({ page }) => {
  await openFinanceSettings(page);
  await expect(page.getByText("Electricity tariff")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Energy / Solar" })).toHaveCount(0);
});
