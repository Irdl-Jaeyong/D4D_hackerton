#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$root/.env" ]]; then set -a; source "$root/.env"; set +a; fi
runtime="${XDG_DATA_HOME:-$HOME/.local/share}/ollama-runtime"
binary="${OLLAMA_BIN:-$runtime/bin/ollama}"
export OLLAMA_HOST="${OLLAMA_HOST:-${OLLAMA_BASE_URL:-http://127.0.0.1:11434}}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-${XDG_DATA_HOME:-$HOME/.local/share}/ollama/models}"
if [[ ! -x "$binary" ]]; then
  echo "Ollama가 없습니다. scripts/install_ollama.sh를 먼저 실행하세요." >&2
  exit 1
fi
mkdir -p "$OLLAMA_MODELS"
exec "$binary" "$@"
