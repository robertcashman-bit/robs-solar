/**
 * One-shot Electron script: decrypt Custody Note settings DB and print QuickFile creds as JSON.
 * Run via: electron scripts/custody-note-export-quickfile.cjs (from custody-note-app cwd)
 */
const { app, safeStorage } = require("electron");
const fs = require("fs");
const path = require("path");

const CUSTODY_APP =
  process.env.CUSTODY_NOTE_APP || path.join(process.env.HOME || "", "custody-note-app");
const initSqlJs = require(path.join(CUSTODY_APP, "node_modules/sql.js"));
const dbCrypto = require(path.join(CUSTODY_APP, "lib/dbCrypto"));

const USER_DATA =
  process.env.CUSTODY_NOTE_USER_DATA ||
  path.join(app.getPath("home"), "Library", "Application Support", "custody-note");

const KEYS = ["quickfileAccountNumber", "quickfileApiKey", "quickfileAppId"];

function readMasterKey() {
  const keyPath = path.join(USER_DATA, "encryption.key");
  if (!fs.existsSync(keyPath)) {
    throw new Error(`Missing encryption key: ${keyPath}`);
  }
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error("Electron safeStorage is not available on this machine.");
  }
  return safeStorage.decryptString(fs.readFileSync(keyPath));
}

async function readQuickFileSettings() {
  const dbPath = path.join(USER_DATA, "attendances.db");
  if (!fs.existsSync(dbPath)) {
    throw new Error(`Missing database: ${dbPath}`);
  }
  const masterKey = readMasterKey();
  const raw = fs.readFileSync(dbPath);
  const plain = dbCrypto.decryptBuffer(raw, masterKey);
  if (!plain) {
    throw new Error("Could not decrypt Custody Note database.");
  }
  const SQL = await initSqlJs();
  const db = new SQL.Database(plain);
  const out = {};
  for (const key of KEYS) {
    const stmt = db.prepare("SELECT value FROM settings WHERE key = ?");
    stmt.bind([key]);
    if (stmt.step()) {
      out[key] = String(stmt.getAsObject().value || "").trim();
    } else {
      out[key] = "";
    }
    stmt.free();
  }
  db.close();
  return out;
}

app.whenReady()
  .then(async () => {
    const settings = await readQuickFileSettings();
    const payload = {
      account_number: settings.quickfileAccountNumber || "",
      api_key: settings.quickfileApiKey || "",
      application_id: settings.quickfileAppId || "",
    };
    if (!payload.account_number || !payload.api_key || !payload.application_id) {
      process.stderr.write(
        "QuickFile credentials are incomplete in Custody Note settings.\n",
      );
      app.exit(2);
      return;
    }
    process.stdout.write(JSON.stringify(payload));
    app.exit(0);
  })
  .catch((err) => {
    process.stderr.write(`${err && err.message ? err.message : err}\n`);
    app.exit(1);
  });
