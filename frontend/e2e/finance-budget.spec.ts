import { expect, test } from "@playwright/test";

import { gotoWhenAuthed } from "./helpers";

test("suggested budgets can be edited, saved, and activated", async ({ page }) => {
  const uniqueName = `E2E Balanced ${Date.now()}`;
  await gotoWhenAuthed(page, "/finance/personal");
  await page.getByPlaceholder("Income").fill("4500");
  await page.getByPlaceholder("Spending").fill("2200");
  await page.getByPlaceholder("Household bills").fill("900");
  await page.getByPlaceholder("Debt repayments").fill("180");
  await page.getByRole("button", { name: "Save snapshot" }).click();
  await expect(page.getByText("Snapshot saved")).toBeVisible();

  await page.goto("/finance/budget");
  await expect(page.getByRole("heading", { name: "Budget" })).toBeVisible();
  await page.getByRole("tab", { name: "Suggested" }).click();
  await expect(page.getByRole("heading", { name: "Balanced" })).toBeVisible();
  await page.getByRole("button", { name: "Use Balanced" }).click();

  const firstAmount = page.getByLabel(/amount$/i).first();
  await expect(firstAmount).toBeVisible();
  const previous = await firstAmount.inputValue();
  const nextValue = String(Number(previous || "0") + 25);
  await firstAmount.fill(nextValue);
  await expect(page.getByText(/Monthly surplus:|Monthly deficit:/)).toBeVisible();

  await page.getByLabel("Budget name").fill(uniqueName);
  await page.getByRole("button", { name: "Save and set active" }).click();
  await expect(page.getByText("Budget saved and set as active")).toBeVisible();

  await page.goto("/finance/debts");
  await page.goto("/finance/budget");
  await page.getByRole("tab", { name: "Suggested" }).click();
  await expect(page.getByText(uniqueName)).toBeVisible();
  await page.getByRole("button", { name: "Open" }).first().click();
  await expect(page.getByLabel("Budget name")).toHaveValue(uniqueName);

  await page.reload();
  await page.getByRole("tab", { name: "Suggested" }).click();
  await expect(page.getByText(uniqueName)).toBeVisible();
  await expect(page.getByText("Active").first()).toBeVisible();

  await page.getByRole("tab", { name: "vs Actual" }).click();
  const firstActual = page.getByLabel(/actual$/i).first();
  await expect(firstActual).toBeVisible();
  await firstActual.fill("12.50");
  await page.getByRole("button", { name: "Save actuals" }).click();
  await expect(page.getByText("Actual spend saved")).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "vs Actual" }).click();
  await expect(page.getByLabel(/actual$/i).first()).toHaveValue("12.5");
});

test("budget editor rejects invalid amounts instead of saving zero", async ({ page }) => {
  await gotoWhenAuthed(page, "/finance/budget");
  await page.getByRole("tab", { name: "Suggested" }).click();
  await page.getByRole("button", { name: "Start blank" }).click();
  await page.getByLabel("Monthly income").fill("not-a-number");
  await page.getByPlaceholder("Add category").fill("Food");
  await page.getByRole("button", { name: "Add category" }).click();
  await page.getByLabel("Food amount").fill("abc");
  await expect(page.getByText("Enter valid pound amounts to see surplus")).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/Invalid text is not saved as £0/)).toBeVisible();
  await page.getByLabel("Monthly income").fill("£1,234.56");
  await page.getByLabel("Food amount").fill("80");
  await expect(page.getByText(/Monthly surplus:/)).toBeVisible();
  await page.getByLabel("Budget name").fill(`E2E Sterling ${Date.now()}`);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Budget saved", { exact: true })).toBeVisible();
});
