#!/usr/bin/env node
/**
 * Fetch QuickFile credentials from Custody Note cloud KV (encrypted blob).
 * Looks for the decrypt helper and KV tokens in several checkout layouts,
 * and can pull KV from the custody-note-website Vercel project when
 * VERCEL_TOKEN is set.
 */
import { existsSync, readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { createRequire } from "module";
import { homedir } from "os";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const allRoot = join(root, "..");
const home = process.env.HOME || homedir();
const require = createRequire(import.meta.url);

function firstExisting(paths) {
  for (const path of paths) {
    if (path && existsSync(path)) return path;
  }
  return null;
}

function findSyncModule() {
  const app = process.env.CUSTODY_NOTE_APP || "";
  return firstExisting([
    app && join(app, "lib/quickfileSettingsSync.js"),
    app && join(app, "custody-note-app-source/lib/quickfileSettingsSync.js"),
    join(allRoot, "custody-note-app/lib/quickfileSettingsSync.js"),
    join(allRoot, "custody-note-app/custody-note-app-source/lib/quickfileSettingsSync.js"),
    join(home, "custody-note-app/lib/quickfileSettingsSync.js"),
    join(home, "custody-note-app/custody-note-app-source/lib/quickfileSettingsSync.js"),
    "/tmp/custody-note-app/custody-note-app-source/lib/quickfileSettingsSync.js",
    "/tmp/other-git/custody-note-app/lib/quickfileSettingsSync.js",
  ]);
}

function loadEnvFile(path) {
  if (!path || !existsSync(path)) return;
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    if (!process.env[key]) process.env[key] = val;
  }
}

function loadWebsiteEnv() {
  const website = process.env.CUSTODY_NOTE_WEBSITE || "";
  const envPath = firstExisting([
    website && join(website, ".env.local"),
    join(allRoot, "custody-note-website/.env.local"),
    join(home, "custody-note-website/.env.local"),
  ]);
  loadEnvFile(envPath);
}

async function vercelJson(url) {
  const token = process.env.VERCEL_TOKEN;
  if (!token) return null;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return null;
  return res.json();
}

async function loadKvFromVercel() {
  if (process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN) return true;
  if (!process.env.VERCEL_TOKEN) return false;
  const listing = await vercelJson("https://api.vercel.com/v9/projects?limit=50");
  const project = (listing?.projects || []).find((item) => item.name === "custody-note-website");
  if (!project) return false;
  const envs = await vercelJson(`https://api.vercel.com/v9/projects/${project.id}/env`);
  for (const key of ["KV_REST_API_URL", "KV_REST_API_TOKEN"]) {
    const row = (envs?.envs || []).find((item) => item.key === key);
    if (!row) continue;
    const detail = await vercelJson(
      `https://api.vercel.com/v9/projects/${project.id}/env/${row.id}?decrypt=true`,
    );
    if (detail?.value) process.env[key] = detail.value;
  }
  return Boolean(process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN);
}

async function kvGet(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) {
    throw new Error("KV_REST_API_URL and KV_REST_API_TOKEN required");
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(["GET", key]),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(`KV GET ${key} failed: ${res.status}`);
  const result = data.result;
  if (typeof result === "string" && (result.startsWith("{") || result.startsWith("["))) {
    try {
      return JSON.parse(result);
    } catch {
      return result;
    }
  }
  return result;
}

async function main() {
  loadWebsiteEnv();
  await loadKvFromVercel();
  const syncPath = findSyncModule();
  if (!syncPath) {
    throw new Error(
      "Could not find lib/quickfileSettingsSync.js. Set CUSTODY_NOTE_APP to the desktop app checkout.",
    );
  }
  const sync = require(syncPath);
  const email = String(process.env.CUSTODY_NOTE_EMAIL || "robertdavidcashman@gmail.com")
    .trim()
    .toLowerCase();

  const userId = await kvGet(`user:email:${email}`);
  if (!userId) {
    throw new Error(`No Custody Note user for email ${email}`);
  }
  const user = await kvGet(`user:${userId}`);
  if (!user?.subscriptionId) {
    throw new Error(`User ${email} has no subscription`);
  }
  const sub = await kvGet(`sub:${user.subscriptionId}`);
  const licenceKey = String(sub?.licenceKey || "").trim();
  if (!licenceKey) {
    throw new Error(`No licence key for ${email}`);
  }

  const row = await kvGet(`qf-settings:${userId}`);
  if (!row?.blob) {
    throw new Error("No QuickFile settings blob on Custody Note server for this account");
  }

  const decrypted = sync.decryptQuickFileSettings(licenceKey, row.blob);
  if (!decrypted?.quickfileAccountNumber || !decrypted?.quickfileApiKey || !decrypted?.quickfileAppId) {
    throw new Error("QuickFile blob decrypted but credentials are incomplete");
  }

  const payload = {
    account_number: decrypted.quickfileAccountNumber,
    api_key: decrypted.quickfileApiKey,
    application_id: decrypted.quickfileAppId,
  };
  process.stdout.write(JSON.stringify(payload));
}

main().catch((err) => {
  process.stderr.write(`${err.message || err}\n`);
  process.exit(1);
});
