#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$root/.env" ]]; then set -a; source "$root/.env"; set +a; fi
docker exec -e "IGN_PARTITION=${IGN_PARTITION:-navis-d4d}" -e IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/tmp/navis_visual "${NAVIS_CONTAINER:-d4d-navis-prep}" ign gazebo -g &
gui_pid=$!
trap 'kill "$gui_pid" 2>/dev/null || true' INT TERM
docker exec -e "IGN_PARTITION=${IGN_PARTITION:-navis-d4d}" "${NAVIS_CONTAINER:-d4d-navis-prep}" python3 /project/scripts/follow_gazebo_camera.py
wait "$gui_pid"
