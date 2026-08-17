import { test as setup } from "@playwright/test";

import { loginAsAdmin } from "./helpers";

const authFile = "e2e/.auth/admin.json";

setup("authenticate as admin", async ({ page }) => {
  await loginAsAdmin(page);
  await page.context().storageState({ path: authFile });
});
