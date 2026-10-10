#!/usr/bin/env bash
set -euo pipefail
set +u
source /opt/ros/humble/setup.bash
set -u
export IGN_PARTITION=navis-d4d-koyul
export IGN_GAZEBO_RESOURCE_PATH=/project/ros_ws/src/navis_sim/models
export ROS_DOMAIN_ID=44
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE=/project/config/fastdds.xml
unset CYCLONEDDS_URI
# Build the vendored Apache-2.0 VRX visual plugin for Fortress.
cmake -S /project/docker/visual -B /tmp/navis_visual -DCMAKE_BUILD_TYPE=Release >/tmp/navis_visual_config.log 2>&1
cmake --build /tmp/navis_visual -j4 >/tmp/navis_visual_build.log 2>&1
export IGN_GAZEBO_SYSTEM_PLUGIN_PATH=/tmp/navis_visual
pids=()
cleanup(){ trap - EXIT INT TERM; for pid in "${pids[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done; exit 0; }
trap cleanup EXIT INT TERM
ign gazebo -s -r /project/ros_ws/src/navis_sim/worlds/prep.sdf & pids+=("$!")
# Wait for the world publishers before creating dozens of subscriptions.
for ((attempt=0; attempt<30; attempt++)); do
  if ign topic -l | grep -q '/navis/USV_02/odometry'; then break; fi
  sleep 1
done
sleep 2
topics=('/world/navis_prep/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock' '/navis/camera/wide@sensor_msgs/msg/Image[ignition.msgs.Image' '/navis/camera/detail@sensor_msgs/msg/Image[ignition.msgs.Image')
mapfile -t vehicles < <(python3 -c 'import json; f=json.load(open("/project/config/fleet.json")); print("\n".join(f"{kind}-{i:02}" for kind,key in [("SHIP","ships"),("UAV","uavs"),("USV","usvs")] for i in range(1,f[key]+1)))')
for vehicle in "${vehicles[@]}"; do
  topics+=("/navis/${vehicle//-/_}/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry")
done
for ((i=0; i<${#topics[@]}; i+=12)); do
  ros2 run ros_gz_bridge parameter_bridge "${topics[@]:i:12}" & pids+=("$!")
done
for group in 0 1 2 3; do
  NAVIS_BRIDGE_GROUP=$group python3 /project/ros_ws/src/navis_bridge/telemetry_node.py & pids+=("$!")
done
python3 /project/scripts/convoy_motion.py & pids+=("$!")
python3 /project/scripts/gazebo_status_bridge.py & pids+=("$!")
wait -n "${pids[@]}"
