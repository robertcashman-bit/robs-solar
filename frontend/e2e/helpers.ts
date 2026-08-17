import { expect, type Page } from "@playwright/test";

const LOGIN_TIMEOUT = 60_000;
const PAGE_TIMEOUT = 30_000;

/** Finance overview is the default landing page after login. */
export async function expectFinanceOverviewAfterLogin(page: Page) {
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible({
    timeout: LOGIN_TIMEOUT,
  });
  await expect(page.getByRole("heading", { name: "Balances" })).toBeVisible({
    timeout: LOGIN_TIMEOUT,
  });
}

/** Solar/Energy is not part of the finance app. */
export async function expectEnergyRemoved(page: Page) {
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "Energy" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Energy / Solar" })).toHaveCount(0);
  await expect(page.getByText("Energy savings")).toHaveCount(0);
}

/** Full login flow — use only when testing sign-in itself. */
export async function loginAsAdmin(page: Page) {
  const email = process.env.E2E_ADMIN_EMAIL ?? "admin";
  const password = process.env.E2E_ADMIN_PASSWORD ?? "change-me-admin";
  await page.goto("/login");
  await expect(page.getByLabel("Email")).toBeVisible({ timeout: PAGE_TIMEOUT });
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in with password" }).click();
  await expectFinanceOverviewAfterLogin(page);
}

export async function loginAsViewer(page: Page) {
  const email = process.env.E2E_VIEWER_EMAIL ?? "viewer";
  const password = process.env.E2E_VIEWER_PASSWORD ?? "change-me-viewer";
  await page.goto("/login");
  await expect(page.getByLabel("Email")).toBeVisible({ timeout: PAGE_TIMEOUT });
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in with password" }).click();
  await expectFinanceOverviewAfterLogin(page);
}

/** Navigate to a protected route (admin session is preloaded via storageState). */
export async function gotoWhenAuthed(page: Page, path: string) {
  await page.goto(path);
  const loading = page.getByRole("status", { name: "Loading session" });
  await loading.waitFor({ state: "hidden", timeout: PAGE_TIMEOUT }).catch(() => undefined);
}

/** Open the finance overview with a pre-authenticated admin session. */
export async function openFinanceOverview(page: Page) {
  await gotoWhenAuthed(page, "/");
  await expectFinanceOverviewAfterLogin(page);
}

/** Open finance settings. Energy / Solar is no longer a settings tab. */
export async function openFinanceSettings(page: Page) {
  await gotoWhenAuthed(page, "/settings");
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible({
    timeout: PAGE_TIMEOUT,
  });
  await expect(page.getByRole("button", { name: "Energy / Solar" })).toHaveCount(0);
}
