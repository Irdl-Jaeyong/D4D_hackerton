#!/usr/bin/env bash
# Start the local Junseok web, Ollama and Gazebo stack from any directory.
set -euo pipefail
script="$(readlink -f -- "${BASH_SOURCE[0]}")"
root="$(cd -- "$(dirname -- "$script")/.." && pwd)"
cd "$root"
[[ -f .env ]] || { echo '먼저 scripts/setup_backend.sh 실행 후 .env를 설정하세요.' >&2; exit 1; }
set -a; source .env; set +a
export NAVIS_WEB_PORT="${NAVIS_WEB_PORT:-18083}"
export NAVIS_BACKEND_URL="${NAVIS_BACKEND_URL:-http://127.0.0.1:$NAVIS_WEB_PORT}"
export NAVIS_CONTAINER="${NAVIS_CONTAINER:-d4d-enter-prep}"
web_unit="${NAVIS_BACKEND_UNIT:-d4d-enter-web}"
sim_unit="${NAVIS_SIM_UNIT:-d4d-enter-sim}"
gui_unit="${NAVIS_GUI_UNIT:-d4d-enter-gui}"
ollama_unit="${NAVIS_OLLAMA_UNIT:-d4d-enter-ollama}"
url="${NAVIS_BACKEND_URL:-http://127.0.0.1:${NAVIS_WEB_PORT:-18083}}"
container="${NAVIS_CONTAINER:-d4d-navis-prep}"
python="$root/backend/.venv/bin/python"

active() { systemctl --user is-active --quiet "$1"; }
launch() {
  local unit="$1" entry="$2"; shift 2
  if active "$unit"; then return; fi
  systemctl --user reset-failed "$unit" >/dev/null 2>&1 || true
  systemd-run --user --unit="$unit" --collect \
    --property="WorkingDirectory=$root" --property=TimeoutStopSec=15 \
    "$@" "$root/scripts/$entry"
}
stop_unit() { systemctl --user stop "$1" 2>/dev/null || true; }

case "${1:-start}" in
  start)
    for dependency in python3 curl docker systemctl systemd-run flock; do
      command -v "$dependency" >/dev/null || { echo "필요한 명령이 없습니다: $dependency" >&2; exit 1; }
    done
    mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/navis"
    exec 9>"${XDG_STATE_HOME:-$HOME/.local/state}/navis/enter.lock"
    flock -n 9 || { echo '다른 D4D_enter 실행이 준비 중입니다.' >&2; exit 1; }
    [[ -x "$python" ]] || "$root/scripts/setup_backend.sh"
    "$python" -c 'import fastapi,uvicorn,httpx' || { echo '백엔드 의존성을 확인하세요.' >&2; exit 1; }
    docker info >/dev/null
    docker image inspect "${NAVIS_ROS_IMAGE:-aac-2026-image:sim}" >/dev/null
    if ! curl -fsS --max-time 3 "${OLLAMA_BASE_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null; then
      echo '[1/4] Ollama 시작'
      launch "$ollama_unit" enter_ollama.sh --property=Restart=on-failure --property=RestartSec=3
    else
      echo '[1/4] 실행 중인 Ollama 사용'
    fi
    "$python" scripts/check_enter.py ollama --timeout 30
    # Only migrate the specifically configured previous D4D services.
    if ! active "$web_unit" && [[ -n "${NAVIS_PREVIOUS_BACKEND_UNIT:-}" ]]; then
      stop_unit "$NAVIS_PREVIOUS_BACKEND_UNIT"
    fi
    if ! active "$sim_unit" && [[ -n "${NAVIS_PREVIOUS_SIM_UNIT:-}" ]]; then
      if [[ -n "${NAVIS_PREVIOUS_GUI_UNIT:-}" ]]; then stop_unit "$NAVIS_PREVIOUS_GUI_UNIT"; fi
      stop_unit "$NAVIS_PREVIOUS_SIM_UNIT"
    fi
    if ! active "$web_unit" && curl -fsS --max-time 2 "$url/api/health" >/dev/null; then
      echo "다른 서버가 $url 을 사용 중입니다. 포트 또는 이전 서비스 설정을 확인하세요." >&2
      exit 1
    fi
    echo '[2/4] 웹 백엔드 시작'
    launch "$web_unit" start_backend.sh --property=Restart=on-failure --property=RestartSec=3
    "$python" scripts/check_enter.py web --timeout 20
    echo '[3/4] Gazebo 및 ROS 브리지 시작'
    launch "$sim_unit" start_sim.sh --property=Restart=on-failure --property=RestartSec=3 \
      --setenv="DISPLAY=${DISPLAY:-:0}" --setenv="XAUTHORITY=${XAUTHORITY:-}"
    "$python" scripts/check_enter.py live --timeout "${NAVIS_START_TIMEOUT:-120}"
    echo '[4/4] Gazebo GUI 시작'
    if [[ -n "${DISPLAY:-}" ]]; then
      launch "$gui_unit" open_gazebo.sh
    else
      echo 'DISPLAY가 없어 GUI는 생략했습니다. 웹 카메라와 데이터는 사용할 수 있습니다.'
    fi
    printf '\n준비 완료: %s/\n모델: %s\n종료: D4D_enter stop\n' "$url" "$OLLAMA_MODEL"
    ;;
  stop)
    stop_unit "$gui_unit"; stop_unit "$sim_unit"; stop_unit "$web_unit"
    echo 'D4D 웹·Gazebo 종료. 공유 Ollama 서비스는 유지합니다.'
    ;;
  status)
    "$python" scripts/check_enter.py status
    for unit in "$web_unit" "$sim_unit" "$gui_unit"; do
      printf '%s: ' "$unit"; systemctl --user is-active "$unit" || true
    done
    ;;
  logs) journalctl --user -u "$web_unit" -u "$sim_unit" -u "$gui_unit" -u "$ollama_unit" -n 70 --no-pager ;;
  *) echo '사용법: D4D_enter [start|stop|status|logs]' >&2; exit 2 ;;
esac
