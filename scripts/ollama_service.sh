#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-status}" in
  start)
    if systemctl --user is-active --quiet d4d-ollama.service; then
      echo "Ollama가 이미 실행 중입니다."
      exit 0
    fi
    systemd-run --user --unit=d4d-ollama --collect "$script_dir/ollama.sh" serve
    ;;
  stop) systemctl --user stop d4d-ollama.service ;;
  status) systemctl --user status d4d-ollama.service ;;
  logs) journalctl --user -u d4d-ollama.service -n 50 --no-pager ;;
  *) echo "사용법: $0 {start|stop|status|logs}" >&2; exit 1 ;;
esac
