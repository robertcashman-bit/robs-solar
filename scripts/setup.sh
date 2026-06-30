#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Setting up Rob's Solar backend..."
cd backend
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example"
fi
cd "$ROOT"

echo "==> Setting up Rob's Solar frontend..."
cd frontend
npm install
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "Created frontend/.env.local from .env.example"
fi
cd "$ROOT"

echo "==> Ensuring lightningcss native binaries (Darwin)..."
bash scripts/ensure-lightningcss.sh

echo "==> Setup complete."
