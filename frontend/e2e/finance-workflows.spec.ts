import { expect, test } from "@playwright/test";

import { gotoWhenAuthed, openFinanceOverview } from "./helpers";

test("finance routes load from navigation", async ({ page }) => {
  await openFinanceOverview(page);
  const routes = [
    ["Personal", "/finance/personal", "Personal Finance"],
    ["Business", "/finance/business", "Business Finance"],
    ["Debts", "/finance/debts", "Debts"],
    ["Cash Flow", "/finance/cash-flow", "Cash Flow"],
    ["Budget", "/finance/budget", "Budget"],
    ["Reports", "/finance/reports", "Reports"],
    ["Connect banks", "/finance/connect", "Connect banks"],
    ["Settings", "/settings", "Settings"],
  ] as const;
  for (const [nav, path, heading] of routes) {
    await page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: nav }).click();
    await expect(page.getByRole("heading", { name: heading, exact: true }).first()).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
  }
});

test("reports and cash flow load and accept existing controls", async ({ page }) => {
  await gotoWhenAuthed(page, "/finance/reports");
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await expect(page.getByLabel("Report month")).toBeVisible();
  await expect(page.getByText("Net worth", { exact: true })).toBeVisible();
  await expect(page.getByText("Energy savings")).toHaveCount(0);
  await expect(page.getByText(/Sunsynk|Octopus Energy|Tesla/i)).toHaveCount(0);

  await gotoWhenAuthed(page, "/finance/cash-flow");
  await expect(page.getByRole("heading", { name: "Cash Flow" })).toBeVisible();
  await page.getByRole("button", { name: "60d" }).click();
  await expect(page.getByText("Horizon", { exact: true })).toBeVisible();
  await expect(page.getByText("60", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Personal" }).click();
  await expect(page.getByRole("heading", { name: "Cash Flow" })).toBeVisible();
  await page.getByRole("button", { name: "DLS Ltd" }).click();
  await expect(page.getByRole("heading", { name: "Cash Flow" })).toBeVisible();
  await page.getByRole("button", { name: "All" }).click();
  await expect(page.getByRole("heading", { name: "Cash Flow" })).toBeVisible();
  await expect(page.getByText("Failed to load cash flow")).toHaveCount(0);
});
