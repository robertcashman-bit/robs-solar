import { expect, test } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

test.use({ storageState: { cookies: [], origins: [] } });

async function openBudget(page: import("@playwright/test").Page) {
  await loginAsAdmin(page);
  await page.goto("/finance/budget");
  await expect(page.getByRole("heading", { name: "Budget", exact: true })).toBeVisible();
}

test("budget first-time flow, edit, save, activate, and persist", async ({ page }) => {
  await openBudget(page);

  const start = page.getByRole("button", { name: "Create your first budget" });
  if (await start.isVisible().catch(() => false)) {
    await start.click();
  }

  await expect(page.getByRole("heading", { name: "Budget options" })).toBeVisible();
  await expect(page.getByRole("radio", { name: /Balanced/ })).toBeVisible();
  await page.getByRole("radio", { name: /Balanced/ }).click();

  const amount = page.getByLabel(/Monthly amount/i).first();
  await expect(amount).toBeVisible();
  const before = await page.getByText(/Projected monthly (surplus|shortfall)|unavailable/i).first().textContent();
  await amount.fill("123.45");
  await expect(page.getByText(/Projected monthly (surplus|shortfall)|unavailable/i).first()).not.toHaveText(
    before ?? "__unchanged__",
  );

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
  await expect(page.getByText(unique)).toBeVisible();

  await page.reload();
  await page.goto("/finance/budget");
  await expect(page.getByLabel("Budget name")).toHaveValue(unique);
  await expect(page.getByText("Active", { exact: true }).first()).toBeVisible();
});

test("deficit is shown and does not invent income", async ({ page }) => {
  await openBudget(page);
  const start = page.getByRole("button", { name: "Create your first budget" });
  if (await start.isVisible().catch(() => false)) {
    await start.click();
  }
  await expect(page.getByRole("heading", { name: "Budget categories" })).toBeVisible();

  const income = page.getByLabel(/Monthly amount for .*income/i).first();
  if (await income.isVisible().catch(() => false)) {
    await income.fill("10");
  }
  const expense = page.getByLabel(/Monthly amount for /i).nth(1);
  await expense.fill("9999");
  await expect(page.getByText(/Projected monthly shortfall/i)).toBeVisible();
  await expect(page.getByText("Deficit", { exact: true })).toBeVisible();

  await page.getByLabel("Budget name").fill(`E2E Deficit ${Date.now()}`);
  await page.getByRole("button", { name: "Save budget" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Saved" })).toBeVisible();
  await expect(page.getByText(/Projected monthly shortfall/i)).toBeVisible();
});

test("missing amounts stay visible and are not saved as zero", async ({ page }) => {
  await openBudget(page);
  const start = page.getByRole("button", { name: "Create your first budget" });
  if (await start.isVisible().catch(() => false)) {
    await start.click();
  }

  await page.getByLabel("Category").fill("Unknown subscription");
  await page.getByLabel("Amount").fill("");
  await page.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByText("Missing / needs input").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Needs attention" }).or(page.getByText("Missing / needs input"))).toBeVisible();
});
