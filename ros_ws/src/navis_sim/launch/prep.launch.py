from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable
from launch_ros.actions import Node

def generate_launch_description():
    world = Path(get_package_share_directory('navis_sim')) / 'worlds' / 'prep.sdf'
    return LaunchDescription([
        SetEnvironmentVariable('IGN_PARTITION', 'navis-d4d-prep'),
        SetEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH', str(world.parent.parent / 'models')),
        ExecuteProcess(cmd=['ign', 'gazebo', '-s', '-r', str(world)], output='screen'),
        Node(package='ros_gz_bridge', executable='parameter_bridge', arguments=[
            *[f'/navis/{v.replace(chr(45),chr(95))}/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry' for v in ['UAV-01','UAV-02','UAV-03','UAV-04','USV-01','USV-02']],
            '/navis/camera@sensor_msgs/msg/Image[ignition.msgs.Image'], output='screen'),
        Node(package='navis_bridge', executable='telemetry_node.py', output='screen'),
    ])
