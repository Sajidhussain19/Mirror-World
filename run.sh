#!/usr/bin/env bash
# One-command local run (macOS/Linux). Put your keys in .env first (see .env.example).
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
echo "Open http://localhost:8000"
uvicorn app.main:app --port 8000
