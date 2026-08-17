import { expect, test } from "@playwright/test";

import { gotoWhenAuthed, openFinanceOverview } from "./helpers";

test("personal asset add, update, and archive", async ({ page }) => {
  const name = `E2E-TEST-asset-${Date.now()}`;
  await gotoWhenAuthed(page, "/finance/personal");
  await page.getByLabel("Account name").fill(name);
  await page.getByLabel("Type").selectOption("pension");
  await page.getByLabel("Balance (£)").fill("12500");
  await page.getByRole("button", { name: "Add account" }).click();
  await expect(page.getByText("Account saved.")).toBeVisible();
  await expect(page.getByText(name)).toBeVisible();
  const created = page.getByText(name).locator("xpath=ancestor::li");
  await expect(created.getByText("£12,500.00")).toBeVisible();

  await openFinanceOverview(page);
  await expect(page.getByText("Pension", { exact: true })).toBeVisible();

  await page.goto("/finance/personal");
  const row = page.getByText(name).locator("xpath=ancestor::li");
  await row.getByRole("button", { name: "Edit" }).click();
  await row.getByLabel("Balance (£)").fill("13000");
  await row.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Account updated.")).toBeVisible();
  await expect(page.getByText(name).locator("xpath=ancestor::li").getByText("£13,000.00")).toBeVisible();

  await page.getByText(name).locator("xpath=ancestor::li").getByRole("button", { name: "Archive" }).click();
  await page.getByRole("button", { name: "Archive" }).last().click();
  await expect(page.getByText("Account removed from active totals.")).toBeVisible();
  await expect(page.getByText(name)).toHaveCount(0);
});

test("personal and business debts stay in their own totals", async ({ page }) => {
  const personal = `E2E-TEST-personal-${Date.now()}`;
  const business = `E2E-TEST-business-${Date.now()}`;
  await gotoWhenAuthed(page, "/finance/debts");

  await page.getByPlaceholder("Name").fill(personal);
  await page.getByPlaceholder("Balance", { exact: true }).fill("300");
  await page.getByPlaceholder("APR %").fill("19");
  await page.getByPlaceholder("Minimum payment").fill("15");
  await page.getByRole("button", { name: "Add debt" }).click();
  await expect(page.getByText("Debt added")).toBeVisible();

  await page.getByPlaceholder("Name").fill(business);
  await page.getByLabel("Debt scope").selectOption("business");
  await page.getByPlaceholder("Balance", { exact: true }).fill("700");
  await page.getByPlaceholder("APR %").fill("8");
  await page.getByPlaceholder("Minimum payment").fill("40");
  await page.getByRole("button", { name: "Add debt" }).click();
  await expect(page.getByText("Debt added")).toBeVisible();

  await expect(page.getByText(/Personal £/)).toBeVisible();
  await expect(page.getByText(/Business £/)).toBeVisible();

  for (const name of [personal, business]) {
    const row = page.getByRole("row", { name: new RegExp(name) });
    await row.getByRole("button", { name: "Archive" }).click();
    await page.getByRole("button", { name: "Archive" }).last().click();
    await expect(page.getByRole("cell", { name })).toHaveCount(0);
  }
});
