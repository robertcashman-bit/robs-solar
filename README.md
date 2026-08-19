# Rob's Finance

<!-- noop: retrigger Vercel production deploy after missed webhook for 13a93483 -->

The folder name `robs-solar` is historical. This repository is **Rob's Finance**. Do not develop or deploy from `All/robs-solar`. See [ONE_TREE.md](./ONE_TREE.md) and `~/WORKSPACE_MAP.md`.

Secure, mobile-friendly browser application for personal and business finance tracking.

**Important:** The browser never talks directly to RS485/Modbus hardware. All reads and writes go through the FastAPI backend and adapter layer.

## Architecture

- **Frontend:** Next.js + TypeScript (`frontend/`)
- **Backend:** FastAPI control bridge (`backend/`)
- **Adapters:** `simulator` (default), `sunsynk_connect` (primary live path), `modbus_tcp` (direct LAN dongle), `home_assistant`, `modbus_bridge`
- **Safety defaults:** `READ_ONLY=true` and `ENABLE_LIVE_WRITES=false` — no live control writes until explicitly enabled

## Quick start

```bash
cd ~/robs-solar
npm run setup
npm run dev
```

- Frontend: http://127.0.0.1:3000
- Backend API: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health

### Default users (change in `backend/.env`)

| User   | Password           | Role   |
|--------|--------------------|--------|
| admin  | change-me-admin    | admin  |
| viewer | change-me-viewer   | viewer |

## Environment variables

See:

- [`backend/.env.example`](backend/.env.example) — all backend configuration
- [`frontend/.env.example`](frontend/.env.example) — `NEXT_PUBLIC_API_BASE_URL`

Key backend settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `READ_ONLY` | `true` | Block all control writes when true |
| `ENABLE_LIVE_WRITES` | `false` | Master gate for live (non-simulator) adapter writes |
| `ADAPTER_MODE` | `simulator` | `simulator`, `sunsynk_connect`, `modbus_tcp`, `home_assistant`, or `modbus_bridge` |
| `SUNSYNK_ENABLE_UNVERIFIED_WRITES` | `false` | Allow attempting unverified Sunsynk writes |
| `SUNSYNK_INVERTER_SN` | (optional) | Inverter serial; auto-discovered from plant detail when empty |
| `METRICS_SAMPLE_INTERVAL_SECONDS` | `60` | Background sampler interval for historical analytics |
| `METRICS_RETENTION_DAYS` | `90` | How long metric samples are kept |
| `TARIFF_IMPORT_RATE` | `0.28` | Default import rate (GBP/kWh) for savings calculations |
| `TARIFF_EXPORT_RATE` | `0.15` | Default export rate (GBP/kWh) |
| `TARIFF_TIMEZONE` | `Europe/London` | Timezone for cheap/peak windows and TOU bands (not server UTC) |
| `AUTO_SCHEDULE_SOC_FLOOR_PCT` | `20` | Daytime battery reserve when auto-align is enabled |
| `PEAK_IMPORT_GUARD_ENABLED` | `true` | Auto-correct peak grid import at high SOC |
| `SECRET_KEY` | (required) | Session signing key |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | admin | Admin user credentials |
| `ADMIN_EMAIL` | `robertdavidcashman@gmail.com` | Extra admin login alias (not a secret) |
| `LUNCHFLOW_API_KEY` | (empty) | Lunch Flow Destinations → API key |
| `VIEWER_USERNAME` / `VIEWER_PASSWORD` | viewer | Read-only user credentials |


## Pages

### Finance (default)

| Route | Description |
|-------|-------------|
| `/` | Finance overview — income, spending, debts, cash flow |
| `/finance/personal` | Personal accounts and snapshots |
| `/finance/business` | Business accounts (QuickFile sync) |
| `/finance/debts` | Debt tracking |
| `/finance/cash-flow` | Cash flow forecast |
| `/finance/budget` | Budget vs actual |
| `/finance/reports` | Reports and exports |
| `/settings` | Banking integrations and app shortcut |

Solar / Energy is not part of this app. `/energy` and the old energy paths redirect to the finance overview.

## Connect personal finance

Overview stays on manual accounts until a live source is connected. Nothing in git invents bank or QuickFile balances.

1. **QuickFile** — if Custody Note already has it, run `bash robs-solar/scripts/connect-personal-finance.sh` on the Mac. Otherwise paste Account number / API key / Application ID in Settings.
2. **Lunch Flow** — in Lunch Flow open Destinations → API, copy the key, then Settings → Lunch Flow → Save / Test / Sync.
3. **TrueLayer** — paste Client ID, secret, and redirect URI in Settings → Open Banking, then Log in to your bank.
4. **Funding Circle** — enter the outstanding loan in Settings, or pull it after a TrueLayer sync.

Hosted Render/Vercel also need `ADMIN_EMAIL`, `LUNCHFLOW_API_KEY`, and the TrueLayer keys in the dashboard (or `scripts/push-render-secrets.sh` / `scripts/push-vercel-env.sh`). The only stated figure this app seeds itself is the pension pot on a live `robs_solar.db`.

## Modbus TCP discovery

When your RS485-WiFi dongle is on the LAN:

```bash
cd backend && source .venv/bin/activate
python scripts/discover_modbus.py
```

Set `MODBUS_HOST` in `.env` and `ADAPTER_MODE=modbus_tcp`. Live writes remain gated by `READ_ONLY` and `ENABLE_LIVE_WRITES`.

## Development commands

```bash
# Full verification loop (lint, typecheck, tests, audits)
npm run verify

# Backend tests only
npm run test:backend

# Frontend unit tests
npm run test:frontend

# End-to-end tests (starts backend + frontend automatically)
npm run test:e2e

# Backend dev server only
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Frontend dev server only
cd frontend && npm run dev
```

## Safety model

1. **Read-only by default** — set `READ_ONLY=false` only when ready for live writes
2. **RBAC** — `viewer` can read metrics; `admin` can write controls and view audit log
3. **Confirmation required** — every frontend control write shows a confirmation dialog
4. **Audit logging** — every attempted write is recorded (including rejected/failed)
5. **Rate limiting** — write endpoints limited per client IP
6. **CSRF protection** — mutating requests require `X-CSRF-Token` header
7. **No invented mappings** — Home Assistant and Modbus write paths return explicit unsupported errors until you configure verified entity/service/register mappings

## Enabling control writes (simulator)

1. Edit `backend/.env`:
   ```
   READ_ONLY=false
   ADAPTER_MODE=simulator
   ```
2. Restart the backend
3. Sign in as `admin`
4. Open **Controls** → set export limit, operating mode, or schedule → confirm
5. Use **Restore last known good** to re-apply the adapter snapshot after a successful write
6. Open **Settings** to review adapter mode, data source, and safety flags (`GET /capabilities`)

## Analytics

The backend runs a read-only background sampler that stores live metrics every 60 seconds (configurable). Use the **Analytics** page for:

- Day / week / month power and battery SOC charts
- Self-consumption breakdown
- Savings and cost estimates based on your tariff

Admins can edit import/export rates under **Settings → Electricity tariff** (`GET/PUT /tariff`).

API endpoints (viewer+):

- `GET /metrics/history?range=day|week|month` — downsampled time series
- `GET /metrics/summary?range=...` — integrated kWh totals and savings

## Sunsynk Connect / Connect Pro (primary live path)

This is the intended live integration for accounts that already use the Sunsynk
Connect web/app service. No Home Assistant required.

> **UNVERIFIED INTEGRATION.** The Sunsynk Connect HTTP API is not officially
> documented for third parties. Authentication follows the same RSA + nonce flow
> as the official www.sunsynk.net web app (`/anonymous/publicKey` then
> `/oauth/token/new`). Metric endpoints are community-inferred. Writes remain
> unverified and double-gated by feature flags.

### Read-only live monitoring

```
ADAPTER_MODE=sunsynk_connect
SUNSYNK_USERNAME=your-account-email
SUNSYNK_PASSWORD=your-account-password
SUNSYNK_PLANT_ID=optional-explicit-plant-id
# SUNSYNK_INVERTER_SN=  # optional — auto-discovered from plant detail when omitted
```

Leave `READ_ONLY=true` and `ENABLE_LIVE_WRITES=false`. The dashboard will show a
purple **Live data** badge (vs the blue **Simulated data** badge in simulator mode).

### Attempting unverified live writes (opt-in, at your own risk)

All three of these must be set, and an admin must still confirm each write:

```
READ_ONLY=false
ENABLE_LIVE_WRITES=true
SUNSYNK_ENABLE_UNVERIFIED_WRITES=true
# SUNSYNK_INVERTER_SN=  # optional if auto-discovered
```

If any flag is missing, write attempts fail fast with a clear error and are still
recorded in the audit log. Sunsynk write paths (export limit, schedule, operating
mode, TOU bands, battery control) are community-inferred and marked unverified —
double-gated by `SUNSYNK_ENABLE_UNVERIFIED_WRITES`.

## Home Assistant read path (secondary/optional)

Configure entity IDs in `backend/.env`:

```
ADAPTER_MODE=home_assistant
HA_BASE_URL=http://your-ha:8123
HA_TOKEN=your-long-lived-token
HA_ENTITY_PV_POWER=sensor.your_pv_power
HA_ENTITY_BATTERY_SOC=sensor.your_battery_soc
...
```

Write support requires verified `HA_SERVICE_*` mappings — not enabled until you confirm them.

## Security

Change `ADMIN_PASSWORD` and `VIEWER_PASSWORD` in `backend/.env` before exposing this
service to any network. The backend logs a startup warning if default passwords
(`change-me-admin` / `change-me-viewer`) are still in use. The **Settings** page
shows read-only mode and live-write flags so you can confirm safety before enabling writes.

## Limitations (v1)

- Sunsynk writes are community-inferred and unverified (gated by feature flags)
- Modbus TCP register mappings are not hardcoded — use a local HTTP Modbus bridge sidecar
- Python 3.11+ in production (Docker/CI); local dev supports 3.9+
- OIDC SSO is optional alongside local username/password auth

## Python upgrade path

```bash
brew install python@3.12
cd backend
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Project structure

```
robs-solar/
  backend/app/adapters/   # Simulator, HA, Modbus bridge
  backend/app/routes/     # REST API
  backend/app/services/   # Audit, control, snapshots
  backend/tests/          # pytest unit + integration
  frontend/src/app/       # Next.js pages
  frontend/src/components/
  frontend/e2e/           # Playwright tests
  scripts/verify.sh       # Full CI-style verification
```

## Hosted deployment (Vercel multi-service — recommended)

The browser app and FastAPI API both run on **one Vercel project** (`robs-solar/vercel.json` routes `/backend/*` to the API). No separate Render service required for the app to work.

```bash
# Automatic repair + deploy (Cloud Agent or local)
VERCEL_TOKEN=xxx bash scripts/repair-hosted.sh

# Or from repo root (all sites)
VERCEL_TOKEN=xxx bash scripts/vercel-deploy-all.sh
```

GitHub Actions also deploys on push to `main` when `VERCEL_TOKEN` is set as a repository secret.

### Optional: Render backend (persistent SQLite)

For always-on background sampling with persistent storage, use Render instead of Vercel serverless API:

```bash
open "https://dashboard.render.com/blueprint/new?repo=https://github.com/robertdavidcashman-droid/All"
# Blueprint path: robs-solar/render.yaml

export BACKEND_URL=https://robs-solar-api.onrender.com
export RENDER_API_KEY=... RENDER_SERVICE_ID=srv-...
bash scripts/push-render-secrets.sh
VERCEL_TOKEN=... DEPLOY_MODE=render-external bash scripts/repair-hosted.sh
```

If the live site shows "Loading session…", run `bash scripts/repair-hosted.sh` (removes broken `BACKEND_URL` localhost proxy and redeploys).

**AI assistant:** sign in as the **admin** user (not viewer) to see **Assistant** in the nav and the dashboard AI card. The backend needs `AI_ENABLED=true` and `OPENAI_API_KEY` — sync from local `.env` with `bash scripts/push-render-secrets.sh` or set in the Vercel/Render dashboard, then redeploy.

## License

Private — for Rob's home solar setup.
