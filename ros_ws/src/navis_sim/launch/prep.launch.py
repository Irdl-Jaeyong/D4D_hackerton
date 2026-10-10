from pathlib import Path
import json
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable, TimerAction
from launch_ros.actions import Node

def generate_launch_description():
    world = Path(get_package_share_directory('navis_sim')) / 'worlds' / 'prep.sdf'
    fleet = json.loads((world.parent.parent/'config/fleet.json').read_text())
    ids = [f'{kind}-{i:02}' for kind,key in [('SHIP','ships'),('UAV','uavs'),('USV','usvs')] for i in range(1,fleet[key]+1)]
    return LaunchDescription([
        SetEnvironmentVariable('IGN_PARTITION', 'navis-d4d-koyul'),
        SetEnvironmentVariable('ROS_DOMAIN_ID', '44'),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        SetEnvironmentVariable('RMW_IMPLEMENTATION', 'rmw_fastrtps_cpp'),
        SetEnvironmentVariable('FASTRTPS_DEFAULT_PROFILES_FILE', str(world.parent.parent/'config/fastdds.xml')),
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', str(world.parent.parent / 'models')),
        ExecuteProcess(cmd=['ign', 'gazebo', '-s', '-r', str(world)], output='screen'),
        TimerAction(period=8.0, actions=[Node(package='ros_gz_bridge', executable='parameter_bridge', arguments=[
            *[f'/navis/{v.replace(chr(45),chr(95))}/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry' for v in ids],
            '/world/navis_prep/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock', '/navis/camera/wide@sensor_msgs/msg/Image[ignition.msgs.Image', '/navis/camera/detail@sensor_msgs/msg/Image[ignition.msgs.Image'], output='screen')]),
        TimerAction(period=9.0, actions=[ExecuteProcess(cmd=['python3',str(world.parent.parent/'scripts/convoy_motion.py')], output='screen')]),
        *[Node(package='navis_bridge', executable='telemetry_node.py', additional_env={'NAVIS_BRIDGE_GROUP':str(g)}, output='screen') for g in range(4)],
    ])
