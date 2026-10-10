#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
set -a; source .env; set +a
export NAVIS_BACKEND_URL="${NAVIS_BACKEND_URL:-http://127.0.0.1:${NAVIS_WEB_PORT:-18082}}"
export IGN_PARTITION="${IGN_PARTITION:-navis-d4d}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-45}"
if [[ -z "${NAVIS_ROS_IMAGE:-}" ]]; then
  if docker image inspect aac-2026-image:sim >/dev/null 2>&1; then
    NAVIS_ROS_IMAGE=aac-2026-image:sim
  else
    NAVIS_ROS_IMAGE=aac-2026-image:x86
  fi
fi
auth_args=()
if [[ -n "${XAUTHORITY:-}" && -f "$XAUTHORITY" ]]; then
  auth_args=(--volume "$XAUTHORITY:/tmp/navis.Xauthority:ro" --env XAUTHORITY=/tmp/navis.Xauthority)
fi
exec docker run --rm --init --name d4d-navis-prep --network host --gpus all \
  --env IGN_IP=127.0.0.1 \
  --env NAVIS_BACKEND_URL --env IGN_PARTITION --env ROS_DOMAIN_ID --env NAVIS_BRIDGE_TOKEN --env DISPLAY --env QT_X11_NO_MITSHM=1 \
  --env NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display \
  --env __NV_PRIME_RENDER_OFFLOAD=1 --env __GLX_VENDOR_LIBRARY_NAME=nvidia \
  --env HOME=/tmp --env BASH_ENV= "${auth_args[@]}" \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$root,dst=/project,readonly" \
  --volume /tmp/.X11-unix:/tmp/.X11-unix:ro \
  --entrypoint /bin/bash "${NAVIS_ROS_IMAGE:-aac-2026-image:sim}" /project/docker/ros/run_prep.sh
