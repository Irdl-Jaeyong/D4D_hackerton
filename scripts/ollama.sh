#!/usr/bin/env bash
set -euo pipefail
runtime="${XDG_DATA_HOME:-$HOME/.local/share}/ollama-runtime"
binary="$runtime/bin/ollama"
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS="${XDG_DATA_HOME:-$HOME/.local/share}/ollama/models"
if [[ ! -x "$binary" ]]; then
  echo "Ollama가 없습니다. scripts/install_ollama.sh를 먼저 실행하세요." >&2
  exit 1
fi
mkdir -p "$OLLAMA_MODELS"
exec "$binary" "$@"
