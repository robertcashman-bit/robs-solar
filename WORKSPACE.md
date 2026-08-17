# Workspace: Rob's Solar

| | |
|---|---|
| **Folder** | `robs-solar/` |
| **Project** | Rob's Finance |
| **Purpose** | Personal/business finance dashboard |
| **Canonical repo** | `robertdavidcashman-droid/All` → this folder |
| **Former repo** | `robertcashman-bit/robs-solar` (archive when ready) |
| **Live site** | Private — runs on your home network / Render |
| **Stack** | Next.js frontend + FastAPI backend |

**Vercel root directory (from `All`):** `robs-solar` — see [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)

## Open as a workspace

**Rob Finance App only (recommended):** from the `All` repo root, open **`rob-finance-app.code-workspace`** in Cursor. You get the finance + solar project only — not the rest of the monorepo.

| Platform | How |
|----------|-----|
| Windows Cloud PC | Double-click **`Rob Finance App`** on the desktop (after `upload/Setup-All-CloudPC.cmd`), or run `upload/Open-Rob-Finance-App.cmd` |
| Mac | Click **Rob's Finance** in the Dock, or the Desktop **RobsFinance.app** icon. Opening this workspace (or `all.code-workspace`) reinstalls the app and puts the Desktop / Dock shortcuts back. |
| Any | **File → Open Workspace** → `rob-finance-app.code-workspace` at the `All` repo root |

**Developer layout:** `robs-solar.code-workspace` (same three roots: app, frontend, backend). If you only have the `robs-solar/` folder checked out, use `robs-solar/robs-solar.code-workspace` inside that directory.

## Run locally

```bash
cd robs-solar
npm run setup
npm run dev
```

- Frontend: http://127.0.0.1:3000
- Backend API: http://127.0.0.1:8000

## More detail

See [`README.md`](README.md) in this folder.
