# Rob's Solar

Secure, mobile-friendly browser application for live monitoring and safe control of a Sunsynk 8kW inverter system via a backend control bridge.

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
| `VIEWER_USERNAME` / `VIEWER_PASSWORD` | viewer | Read-only user credentials |


## Pages

| Route | Description |
|-------|-------------|
| `/` | Live dashboard (WebSocket with polling fallback) |
| `/analytics` | Historical charts and savings summary |
| `/octopus` | Agile half-hourly prices (requires `OCTOPUS_API_KEY`) |
| `/forecast` | 3-day solar generation forecast (Open-Meteo) |
| `/scheduler` | TOU schedule presets and timeline (admin) |
| `/controls` | Export limit, mode, battery, force charge/discharge (admin) |
| `/alerts` | SOC, import, pricing, and connectivity alerts |
| `/audit` | Control write audit log (admin) |
| `/settings` | Safety flags, hardware info, tariff, backup/restore |

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
recorded in the audit log. Schedule and operating-mode writes remain unsupported
for the Sunsynk adapter (mappings unverified); export limit is the only inferred
write path.

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

- Sunsynk schedule and operating-mode writes remain unverified (export limit only)
- Modbus register mappings are not hardcoded — use a local HTTP Modbus bridge sidecar
- Python 3.9.6 supported (upgrade to 3.12+ recommended for production)
- Local username/password auth (designed to be replaceable with SSO later)
- Schedule and operating mode UI/backend endpoints exist; simulator adapter supports them; HA/Modbus writes remain unverified

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

## Hosted deployment (Vercel + Render)

The browser app runs on **Vercel**; the FastAPI API runs on **Render** (always-on Docker + persistent SQLite disk). The frontend proxies `/backend/*` to the hosted API via `BACKEND_URL`, so login cookies stay same-origin.

```bash
# 1. Backend — one-time Render blueprint (connect GitHub repo)
open "https://dashboard.render.com/blueprint/new?repo=https://github.com/robertcashman-bit/robs-solar"

# 2. After Render gives you a URL (e.g. https://robs-solar-api.onrender.com):
export BACKEND_URL=https://robs-solar-api.onrender.com
bash scripts/push-render-secrets.sh   # needs RENDER_API_KEY + RENDER_SERVICE_ID

# 3. Frontend — Vercel production deploy
bash scripts/deploy-hosted.sh
```

Set `APP_ENV=production` on Render (in `render.yaml`). Change default passwords before going public.

**AI assistant:** sign in as the **admin** user (not viewer) to see **Assistant** in the nav and the dashboard AI card. The backend needs `AI_ENABLED=true` and `OPENAI_API_KEY` — sync from local `.env` with `bash scripts/push-render-secrets.sh` or set in the Vercel/Render dashboard, then redeploy.

## License

Private — for Rob's home solar setup.
