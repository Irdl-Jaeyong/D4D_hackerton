#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
exec backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port "${NAVIS_WEB_PORT:-18082}"
