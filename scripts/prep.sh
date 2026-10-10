#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$root/.env" ]]; then set -a; source "$root/.env"; set +a; fi
backend_unit="${NAVIS_BACKEND_UNIT:-d4d-navis-backend}"
sim_unit="${NAVIS_SIM_UNIT:-d4d-navis-sim}"
backend_url="${NAVIS_BACKEND_URL:-http://127.0.0.1:${NAVIS_WEB_PORT:-18082}}"
case "${1:-status}" in
 start)
  "$root/scripts/ollama_service.sh" start
  systemctl --user is-active --quiet "$backend_unit" || systemd-run --user --unit="$backend_unit" --collect "$root/scripts/start_backend.sh"
  ready=false
  for ((attempt=0; attempt<20; attempt++)); do
    if curl -fsS "$backend_url/api/health" >/dev/null 2>&1; then ready=true; break; fi
    sleep 0.5
  done
  if [[ "$ready" != true ]]; then echo "Backend did not become ready: $backend_url" >&2; exit 1; fi
  if ! systemctl --user is-active --quiet "$sim_unit"; then
    systemd-run --user --unit="$sim_unit" --collect --property=TimeoutStopSec=10 --setenv="DISPLAY=${DISPLAY:-:0}" --setenv="XAUTHORITY=${XAUTHORITY:-}" "$root/scripts/start_sim.sh"
  fi
  echo "Web: $backend_url (시뮬레이션 준비까지 수 초 소요)"
  ;;
 stop)
  if docker container inspect d4d-navis-prep >/dev/null 2>&1; then docker stop -t 5 d4d-navis-prep >/dev/null; fi
  systemctl --user stop "$sim_unit.service" 2>/dev/null || true
  systemctl --user stop "$backend_unit.service" || true
  ;;
 status)
  systemctl --user --no-pager status "$backend_unit" "$sim_unit" || true
  ;;
 *) echo "사용법: $0 {start|stop|status}" >&2; exit 1;;
esac
