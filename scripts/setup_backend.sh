#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.env')
if not p.exists():
    p.write_text('OLLAMA_BASE_URL=http://127.0.0.1:11434\nOLLAMA_MODEL=minicpm-v4.5:latest\nNAVIS_BRIDGE_TOKEN='+secrets.token_hex(32)+'\n')
    p.chmod(0o600)
PY
