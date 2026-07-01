import { expect, type Page } from "@playwright/test";

const LOGIN_TIMEOUT = 60_000;
const PAGE_TIMEOUT = 30_000;

/** Dashboard home is ready when live metrics or the simulator block panel is visible. */
export async function expectHomeAfterLogin(page: Page) {
  await expect(
    page
      .getByLabel("Live power now")
      .or(page.getByRole("heading", { name: "Live inverter data required" })),
  ).toBeVisible({ timeout: LOGIN_TIMEOUT });
}

/** Full login flow — use only when testing sign-in itself. */
export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("change-me-admin");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expectHomeAfterLogin(page);
}

export async function loginAsViewer(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("viewer");
  await page.getByLabel("Password").fill("change-me-viewer");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expectHomeAfterLogin(page);
}

/** Navigate to a protected route (admin session is preloaded via storageState). */
export async function gotoWhenAuthed(page: Page, path: string) {
  await page.goto(path);
  const loading = page.getByRole("status", { name: "Loading session" });
  await loading.waitFor({ state: "hidden", timeout: PAGE_TIMEOUT }).catch(() => undefined);
}

/** Open the dashboard with a pre-authenticated admin session. */
export async function openDashboard(page: Page) {
  await gotoWhenAuthed(page, "/");
  await expectHomeAfterLogin(page);
}
