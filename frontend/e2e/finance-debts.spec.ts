import { expect, test } from "@playwright/test";

import { gotoWhenAuthed, openFinanceOverview } from "./helpers";

test("debt create, total, edit, archive", async ({ page }) => {
  const name = `E2E-TEST-debt-${Date.now()}`;
  await gotoWhenAuthed(page, "/finance/debts");
  await page.getByPlaceholder("Name").fill(name);
  await page.getByPlaceholder("Balance", { exact: true }).fill("900");
  await page.getByPlaceholder("APR %").fill("22.9");
  await page.getByPlaceholder("Minimum payment").fill("35");
  await page.getByRole("button", { name: "Add debt" }).click();
  await expect(page.getByText("Debt added")).toBeVisible();
  await expect(page.getByRole("cell", { name })).toBeVisible();

  await openFinanceOverview(page);
  await expect(page.getByText("Personal debts", { exact: true })).toBeVisible();

  await page.goto("/finance/debts");
  const row = page.getByRole("row", { name: new RegExp(name) });
  await row.getByRole("button", { name: "Edit" }).click();
  await page.getByPlaceholder("Balance", { exact: true }).fill("850");
  await page.getByRole("button", { name: "Update debt" }).click();
  await expect(page.getByText("Debt updated")).toBeVisible();
  await expect(row.getByText("£850.00")).toBeVisible();

  await row.getByRole("button", { name: "Archive" }).click();
  await page.getByRole("button", { name: "Archive" }).last().click();
  await expect(page.getByText("Debt archived")).toBeVisible();
  await expect(page.getByRole("cell", { name })).toHaveCount(0);
});
