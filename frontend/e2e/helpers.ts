import { expect, type Page } from "@playwright/test";

// Generous: the first hit to /login and the dashboard each trigger a cold
// Next dev compile, which can be slow under parallel CPU contention.
const LOGIN_TIMEOUT = 30000;

export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("change-me-admin");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByLabel("Live power now")).toBeVisible({ timeout: LOGIN_TIMEOUT });
}

export async function loginAsViewer(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("viewer");
  await page.getByLabel("Password").fill("change-me-viewer");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByLabel("Live power now")).toBeVisible({ timeout: LOGIN_TIMEOUT });
}
