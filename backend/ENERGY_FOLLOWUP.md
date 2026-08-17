# Energy / solar API follow-up

Rob's Finance is finance-first. Public solar/energy HTTP routes were removed from
`app/main.py` so the hosted API no longer exposes Sunsynk, Octopus, metrics,
controls, forecast, tariff, alerts, capabilities, websocket, or related surfaces.

Still present in-tree (not mounted):

- `app/adapters/*` (including `sunsynk_auth` MD5 usage Bandit flags)
- `app/routes/{sunsynk,octopus,metrics,controls,forecast,...}.py`
- Energy unit tests under `tests/unit/`
- Energy integration tests (skipped via `tests/conftest.py` collection hook)

Finance keeps QuickFile, Lunch Flow, TrueLayer, Tesla finance settings, Neon/Blob
backups, and auth. Delete or quarantine the leftover energy modules in a later
pass once no external clients depend on them.
