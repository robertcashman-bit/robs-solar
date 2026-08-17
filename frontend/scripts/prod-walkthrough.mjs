/**
 * Logged-in production walkthrough for Rob's Finance.
 * Usage (from frontend/):
 *   node scripts/prod-walkthrough.mjs
 * Reads ../.env.production.walkthrough for ADMIN_USERNAME / ADMIN_PASSWORD.
 */
import { chromium } from "@playwright/test";
import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "../..");
const BASE = process.env.PROD_BASE_URL || "https://robs-solar.vercel.app";
const ENV_FILE = resolve(ROOT, ".env.production.walkthrough");

function loadEnv(path) {
  const out = {};
  if (!existsSync(path)) return out;
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    let v = t.slice(i + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    out[t.slice(0, i).trim()] = v;
  }
  return out;
}

const env = loadEnv(ENV_FILE);
const email = process.env.E2E_ADMIN_EMAIL || env.ADMIN_USERNAME || env.ADMIN_EMAIL;
const password = process.env.E2E_ADMIN_PASSWORD || env.ADMIN_PASSWORD;

const ROUTES = [
  ["/", "Overview"],
  ["/finance/personal", "Personal Finance"],
  ["/finance/business", "Business Finance"],
  ["/finance/debts", "Debts"],
  ["/finance/cash-flow", "Cash Flow"],
  ["/finance/budget", "Budget"],
  ["/finance/transactions", "Transactions"],
  ["/finance/reports", "Reports"],
  ["/finance/upcoming", "Upcoming money"],
  ["/finance/connect", "Connect banks"],
  ["/finance/import", "Import statements"],
  ["/finance/data-quality", "Data quality"],
  ["/settings", "Settings"],
];

const FAIL_TEXT =
  /Failed to load|Something went wrong|Unhandled|Internal Server Error|Not authenticated|Widget crashed|Application error/i;

async function main() {
  if (!email || !password) {
    console.error("Missing ADMIN_USERNAME / ADMIN_PASSWORD for production login");
    process.exit(2);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const findings = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  page.on("response", (res) => {
    const url = res.url();
    if (!url.includes("/backend/") && !url.includes("/api/")) return;
    if (res.status() >= 500) {
      failedRequests.push(`${res.status()} ${url}`);
    }
  });

  console.log(`Base: ${BASE}`);
  console.log(`Login as: ${email.includes("@") ? email.replace(/(.{2}).+(@.+)/, "$1***$2") : email}`);

  async function uiLoginOnce() {
    await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.locator("#login-email").fill(email);
    await page.locator("#current-password").fill(password);
    const [uiLogin] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/auth/login") && r.request().method() === "POST",
        { timeout: 45_000 },
      ),
      page.getByRole("button", { name: /Sign in with password|Sign in/ }).click(),
    ]);
    if (!uiLogin.ok()) {
      throw new Error(`login HTTP ${uiLogin.status()}: ${(await uiLogin.text()).slice(0, 160)}`);
    }
    await page.getByRole("heading", { name: "Overview" }).waitFor({ timeout: 60_000 });
  }

  let loggedIn = false;
  let lastLoginError = "";
  for (let attempt = 1; attempt <= 4; attempt += 1) {
    try {
      await uiLoginOnce();
      findings.push({ route: "/login", ok: true, note: `UI password login succeeded (attempt ${attempt})` });
      loggedIn = true;
      break;
    } catch (err) {
      lastLoginError = String(err).slice(0, 240);
      console.log(`login attempt ${attempt} failed: ${lastLoginError}`);
      await page.waitForTimeout(1500 * attempt);
    }
  }
  if (!loggedIn) {
    findings.push({ route: "/login", ok: false, note: `login failed after retries: ${lastLoginError}` });
    console.log(JSON.stringify({ findings, consoleErrors, pageErrors, failedRequests }, null, 2));
    await browser.close();
    process.exit(1);
  }

  // Wait for overview balances / figures to settle
  await page.waitForTimeout(2500);

  for (const [path, heading] of ROUTES) {
    const beforeFail = failedRequests.length;
    const beforePage = pageErrors.length;
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(1800);

    const headingVisible = await page
      .getByRole("heading", { name: heading, exact: true })
      .first()
      .isVisible()
      .catch(() => false);
    const bodyText = await page.locator("body").innerText().catch(() => "");
    const failMatch = bodyText.match(FAIL_TEXT);
    const stillOnLogin = page.url().includes("/login");
    const newFails = failedRequests.slice(beforeFail);
    const newPageErrors = pageErrors.slice(beforePage);

    const ok =
      headingVisible &&
      !stillOnLogin &&
      !failMatch &&
      newFails.length === 0 &&
      newPageErrors.length === 0;

    findings.push({
      route: path,
      ok,
      headingVisible,
      failText: failMatch ? failMatch[0] : null,
      apiFails: newFails,
      pageErrors: newPageErrors,
      url: page.url(),
    });
    console.log(`${ok ? "PASS" : "FAIL"} ${path}`);
  }

  // Light interaction checks on key pages
  await page.goto(`${BASE}/finance/cash-flow`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1000);
  for (const label of ["7d", "30d", "60d", "Personal", "DLS Ltd", "All"]) {
    const btn = page.getByRole("button", { name: label, exact: true });
    if (await btn.count()) {
      await btn.first().click().catch(() => undefined);
      await page.waitForTimeout(700);
    }
  }
  const cashFail = (await page.locator("body").innerText()).match(FAIL_TEXT);
  findings.push({
    route: "/finance/cash-flow#controls",
    ok: !cashFail,
    failText: cashFail ? cashFail[0] : null,
  });

  await page.goto(`${BASE}/finance/transactions`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
  const txBody = await page.locator("body").innerText();
  findings.push({
    route: "/finance/transactions#content",
    ok: !FAIL_TEXT.test(txBody),
    note: txBody.includes("No transactions")
      ? "empty transactions (ok if no imports)"
      : "has transaction content",
  });

  await page.goto(`${BASE}/settings`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
  const settingsText = await page.locator("body").innerText();
  findings.push({
    route: "/settings#health",
    ok: !FAIL_TEXT.test(settingsText),
    note: /Web backup:\s*(configured|not configured)/i.test(settingsText)
      ? settingsText.match(/Web backup:\s*(configured|not configured)/i)?.[0]
      : "health panel text not found",
  });

  await browser.close();

  const failed = findings.filter((f) => !f.ok);
  console.log("\n=== SUMMARY ===");
  console.log(`Passed: ${findings.filter((f) => f.ok).length}/${findings.length}`);
  if (failed.length) {
    console.log("Failures:");
    for (const f of failed) console.log(JSON.stringify(f));
  }
  if (consoleErrors.length) {
    console.log("\nConsole errors (sample):");
    for (const e of consoleErrors.slice(0, 15)) console.log("-", e.slice(0, 200));
  }
  if (failedRequests.length) {
    console.log("\n5xx API:");
    for (const e of failedRequests) console.log("-", e);
  }

  process.exit(failed.length ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
