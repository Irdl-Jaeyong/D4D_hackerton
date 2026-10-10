#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-status}" in
 start)
  "$root/scripts/ollama_service.sh" start
  systemctl --user is-active --quiet d4d-navis-backend || systemd-run --user --unit=d4d-navis-backend --collect "$root/scripts/start_backend.sh"
  for ((attempt=0; attempt<20; attempt++)); do
    if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
  if ! systemctl --user is-active --quiet d4d-navis-sim; then
    systemd-run --user --unit=d4d-navis-sim --collect --property=TimeoutStopSec=10 --setenv="DISPLAY=${DISPLAY:-:0}" --setenv="XAUTHORITY=${XAUTHORITY:-}" "$root/scripts/start_sim.sh"
  fi
  echo "Web: http://127.0.0.1:8000 (시뮬레이션 준비까지 수 초 소요)"
  ;;
 stop)
  if docker container inspect d4d-navis-prep >/dev/null 2>&1; then docker stop -t 5 d4d-navis-prep >/dev/null; fi
  systemctl --user stop d4d-navis-sim.service 2>/dev/null || true
  systemctl --user stop d4d-navis-backend.service || true
  ;;
 status)
  systemctl --user --no-pager status d4d-navis-backend d4d-navis-sim || true
  ;;
 *) echo "사용법: $0 {start|stop|status}" >&2; exit 1;;
esac
