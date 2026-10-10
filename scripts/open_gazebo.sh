#!/usr/bin/env bash
set -euo pipefail
docker exec -e IGN_PARTITION=navis-d4d-koyul d4d-navis-prep ign gazebo -g &
gui_pid=$!
trap 'kill "$gui_pid" 2>/dev/null || true' INT TERM
docker exec -e IGN_PARTITION=navis-d4d-koyul d4d-navis-prep python3 /project/scripts/follow_gazebo_camera.py
wait "$gui_pid"
