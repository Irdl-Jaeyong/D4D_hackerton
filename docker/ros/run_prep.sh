#!/usr/bin/env bash
set -euo pipefail
set +u
source /opt/ros/humble/setup.bash
set -u
export IGN_PARTITION=navis-d4d-prep
export IGN_GAZEBO_RESOURCE_PATH=/project/ros_ws/src/navis_sim/models
export ROS_DOMAIN_ID=44
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset CYCLONEDDS_URI
pids=()
cleanup(){ trap - EXIT INT TERM; for pid in "${pids[@]}"; do kill -TERM "$pid" 2>/dev/null || true; done; exit 0; }
trap cleanup EXIT INT TERM
ign gazebo -s -r /project/ros_ws/src/navis_sim/worlds/prep.sdf & pids+=("$!")
topics=('/navis/camera@sensor_msgs/msg/Image[ignition.msgs.Image')
for vehicle in UAV-01 UAV-02 UAV-03 UAV-04 USV-01 USV-02; do
  topics+=("/navis/${vehicle//-/_}/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry")
done
ros2 run ros_gz_bridge parameter_bridge "${topics[@]}" & pids+=("$!")
python3 /project/ros_ws/src/navis_bridge/telemetry_node.py & pids+=("$!")
wait -n "${pids[@]}"
