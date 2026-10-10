#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
mkdir -p outputs/fuel_download ros_ws/src/navis_sim/models/x3_uav
# Download official assets to the local ignored cache; keep current containers unchanged.
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/download --env BASH_ENV= \
 --volume "$root/outputs/fuel_download:/download" --entrypoint /bin/bash \
 "${NAVIS_ROS_IMAGE:-aac-2026-image:sim}" -c 'ign fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/X3 UAV/4"; cp /usr/share/ignition/ignition-gazebo6/worlds/quadcopter.sdf /download/quadcopter_original.sdf'
python3 - <<'PY'
from pathlib import Path
import shutil
src=next(Path('outputs/fuel_download').rglob('x3 uav/4/model.sdf')).parent
dst=Path('ros_ws/src/navis_sim/models/x3_uav')
shutil.copytree(src,dst,dirs_exist_ok=True)
shutil.copy('outputs/fuel_download/quadcopter_original.sdf','outputs/quadcopter_original.sdf')
PY
python3 scripts/add_quadcopter.py
