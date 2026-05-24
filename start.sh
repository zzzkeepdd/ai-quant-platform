#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/data_cache"
mkdir -p "$ROOT/backend/data_cache"
(cd "$ROOT/backend" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
(cd "$ROOT/frontend" && npm run dev) &
wait
