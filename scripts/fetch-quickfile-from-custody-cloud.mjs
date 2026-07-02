#!/usr/bin/env node
/**
 * Fetch QuickFile credentials from Custody Note cloud KV (encrypted blob).
 * Uses custody-note-website/.env.local for KV access and custody-note-app for decrypt.
 */
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { createRequire } from "module";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const websiteRoot = process.env.CUSTODY_NOTE_WEBSITE || join(process.env.HOME || "", "custody-note-website");
const custodyAppRoot = process.env.CUSTODY_NOTE_APP || join(process.env.HOME || "", "custody-note-app");
const require = createRequire(import.meta.url);
const sync = require(join(custodyAppRoot, "lib/quickfileSettingsSync.js"));

function loadEnvLocal() {
  const path = join(websiteRoot, ".env.local");
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

async function kvGet(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) {
    throw new Error("KV_REST_API_URL and KV_REST_API_TOKEN required in custody-note-website/.env.local");
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
  loadEnvLocal();
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
