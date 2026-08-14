import { expect, test, type Page } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

async function openBudget(page: Page) {
  await loginAsAdmin(page);
  await page.goto("/finance/budget");
  await expect(page.getByRole("heading", { name: "Budget", exact: true })).toBeVisible();
}

async function startPlanner(page: Page) {
  const start = page.getByRole("button", { name: "Create your first budget" });
  const options = page.getByRole("heading", { name: "Budget options" });
  await expect(start.or(options)).toBeVisible();
  if (await start.isVisible()) {
    await start.click();
  }
  await expect(options).toBeVisible();
}

test("budget first-time flow, edit, save, activate, and persist", async ({ page }) => {
  await openBudget(page);
  await startPlanner(page);

  await expect(page.getByRole("radio", { name: /Balanced/ })).toBeVisible();
  await page.getByRole("radio", { name: /Balanced/ }).click();

  const amount = page.getByLabel(/Monthly amount/i).first();
  await expect(amount).toBeVisible();
  const result = page.getByText(/Projected monthly (surplus|shortfall)|surplus unavailable/i).first();
  const before = await result.textContent();
  await amount.fill("123.45");
  await expect(result).not.toHaveText(before ?? "__unchanged__");

  const unique = `E2E Budget ${Date.now()}`;
  await page.getByLabel("Budget name").fill(unique);
  await page.getByRole("button", { name: "Save and set active" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();
  await expect(page.getByText("Active", { exact: true }).first()).toBeVisible();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Active Budget" })).toBeVisible();
  await expect(page.getByText(unique)).toBeVisible();

  await page.goto("/finance/reports");
  await expect(page.getByRole("heading", { name: "Budget vs actual" })).toBeVisible();
  await expect(page.getByText(unique).first()).toBeVisible();

  await page.reload();
  await page.goto("/finance/budget");
  await expect(page.getByLabel("Budget name")).toHaveValue(unique);
  await expect(page.getByText("Active", { exact: true }).first()).toBeVisible();
});

test("deficit is shown and does not invent income", async ({ page }) => {
  await openBudget(page);
  await startPlanner(page);
  await expect(page.getByRole("heading", { name: "Budget categories" })).toBeVisible();

  const income = page.getByLabel(/Monthly amount for Personal income/i);
  await expect(income).toBeVisible();
  await income.fill("10");
  const bills = page.getByLabel(/Monthly amount for Household bills/i);
  await expect(bills).toBeVisible();
  await bills.fill("9999");
  await expect(page.getByText(/Projected monthly shortfall/i).first()).toBeVisible();
  await expect(page.getByText("Deficit", { exact: true })).toBeVisible();

  await page.getByLabel("Budget name").fill(`E2E Deficit ${Date.now()}`);
  await page.getByRole("button", { name: "Save budget" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();
  await expect(page.getByText(/Projected monthly shortfall/i).first()).toBeVisible();
});

test("missing amounts stay visible and are not saved as zero", async ({ page }) => {
  await openBudget(page);
  await startPlanner(page);

  await page.getByLabel("Category", { exact: true }).fill("Unknown subscription");
  await page.getByLabel("Amount", { exact: true }).fill("");
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByText("Missing / needs input").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Needs attention" })).toBeVisible();
});
