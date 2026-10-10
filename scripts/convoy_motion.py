#!/usr/bin/env python3
"""Gazebo convoy trajectory demo, driven by simulation time.

The Bernoulli figure-eight curve is independently implemented from the
mathematical pattern documented by ModalAI's VOXL flight example. It is
mapped to spherical coordinates to preserve a hemispherical formation.
This does not run PX4, ArduPilot, hydrodynamics, or a flight controller.
"""
import json
import math
import signal
import subprocess
from pathlib import Path

FLEET = json.loads((Path(__file__).resolve().parents[1]/'config/fleet.json').read_text())
MOTION = FLEET['motion']
CAMERA = FLEET['camera']


def figure_eight(angle):
    """Normalized Bernoulli lemniscate and its analytic tangent."""
    s,c=math.sin(angle),math.cos(angle)
    d=1+s*s
    scale=2*math.sqrt(2)
    return (c/d, scale*c*s/d,
            -s*(3-s*s)/(d*d), scale*(1-3*s*s)/(d*d))


def fleet_poses(t, camera=None):
    """Pure trajectory function, with continuous positions and headings."""
    camera=CAMERA if camera is None else camera
    forward=MOTION['ship_speed']*t
    result={}
    def add(name,x,y,z,yaw=0,pitch=0):
        result[name]={'x':x,'y':y,'z':z,'yaw':yaw,'pitch':pitch}
    for i in range(FLEET['ships']):
        add(f'SHIP-{i+1:02}',forward+i*90,0,2.4)
    # Leader-relative perimeter offsets. Continuous handover, with forward
    # velocity at all points, instead of abrupt stop-and-go sector changes.
    rx,ry=MOTION['escort_radii'];omega=MOTION['escort_angular_speed']
    for i in range(FLEET['usvs']):
        a=2*math.pi*i/FLEET['usvs']+omega*t
        x=forward+rx*math.cos(a);y=ry*math.sin(a)
        dx=MOTION['ship_speed']-rx*math.sin(a)*omega
        dy=ry*math.cos(a)*omega
        add(f'USV-{i+1:02}',x,y,.7,math.atan2(dy,dx))
    # Five latitude rings cover the upper sphere. A small figure eight in
    # longitude / latitude remains on that sphere, including at the crossing.
    latitudes=MOTION['hemisphere_latitudes_deg']
    count=FLEET['uavs'];rings=len(latitudes);radius=MOTION['hemisphere_radius']
    step=2*math.pi/MOTION['figure_eight_period']
    for i in range(count):
        ring=i%rings;slot=i//rings
        ring_count=(count-1-ring)//rings+1
        direction=1 if ring%2==0 else -1
        angle=step*t+2*math.pi*slot/ring_count+.35*ring
        ex,ey,tx,ty=figure_eight(angle)
        latitude=math.radians(latitudes[ring])+MOTION['figure_eight_latitude_amplitude']*ey
        longitude=(2*math.pi*slot/ring_count
                   +direction*MOTION['hemisphere_rotation_rate']*t
                   +MOTION['figure_eight_longitude_amplitude']*ex)
        dlat=MOTION['figure_eight_latitude_amplitude']*ty*step
        dlon=(direction*MOTION['hemisphere_rotation_rate']
              +MOTION['figure_eight_longitude_amplitude']*tx*step)
        cl,sl=math.cos(latitude),math.sin(latitude)
        cp,sp=math.cos(longitude),math.sin(longitude)
        x=forward+radius*cl*cp;y=radius*cl*sp
        z=MOTION['hemisphere_center_height']+radius*sl
        dx=MOTION['ship_speed']+radius*(-sl*dlat*cp-cl*sp*dlon)
        dy=radius*(-sl*dlat*sp+cl*cp*dlon)
        add(f'UAV-{i+1:02}',x,y,z,math.atan2(dy,dx))
    for name,p in list(result.items()):
        if name.startswith(('SHIP-','USV-')):
            add('wake_'+name,p['x'],p['y'],-.06,p['yaw'])
    ox,oy,oz=camera['offset']
    add('fleet_observer',forward+ox,oy,oz,camera['yaw'],camera['pitch'])
    # Recenter the purely visual, flat ocean so the demo never leaves it.
    add('ocean',forward,0,-.25)
    return result


def pose_message(name,p):
    cy,sy=math.cos(p['yaw']/2),math.sin(p['yaw']/2)
    cp,sp=math.cos(p['pitch']/2),math.sin(p['pitch']/2)
    return f'name:"{name}" position {{x:{p["x"]:.5f} y:{p["y"]:.5f} z:{p["z"]:.5f}}} orientation {{w:{cy*cp:.7f} x:{-sy*sp:.7f} y:{cy*sp:.7f} z:{sy*cp:.7f}}}'


def poses(t, camera=None):
    return ' '.join('pose {'+pose_message(name,p)+'}' for name,p in fleet_poses(t,camera).items() if name!='fleet_observer')


def main():
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import ExternalShutdownException
    from rclpy.qos import qos_profile_sensor_data
    from rosgraph_msgs.msg import Clock
    class Convoy(Node):
        def __init__(self):
            super().__init__('navis_convoy')
            self.origin=None;self.elapsed=None;self.last_sent=None;self.failures=0
            self.clock_stamp=None
            self.clock_subscription=self.create_subscription(Clock,'/world/navis_prep/clock',self.clock,qos_profile_sensor_data)
            self.timer=self.create_timer(.1,self.update)
            self.get_logger().info('Simulation-time convoy: straight leader, continuous USV handover, 40 UAV hemispherical figure-eight patrols')
        def clock(self,msg):
            stamp=msg.clock.sec+msg.clock.nanosec/1e9
            # A delayed clock packet must never move the convoy backwards.
            if self.clock_stamp is not None and stamp<=self.clock_stamp:return
            self.clock_stamp=stamp
            if self.origin is None:self.origin=stamp
            self.elapsed=stamp-self.origin
        def update(self):
            if self.elapsed is None or self.elapsed==self.last_sent:return
            t=self.elapsed
            try:
                response=subprocess.run(['ign','service','-s','/world/navis_prep/set_pose_vector','--reqtype','ignition.msgs.Pose_V','--reptype','ignition.msgs.Boolean','--timeout','1200','--req',poses(t)],capture_output=True,text=True,timeout=1.5)
                if response.returncode or 'true' not in response.stdout:
                    self.failures+=1
                    if self.failures%10==1:self.get_logger().warning('Pose update failed: '+response.stderr[:160])
                else:self.failures=0;self.last_sent=t
            except subprocess.TimeoutExpired:self.get_logger().warning('Pose update timed out')
    rclpy.init();node=Convoy()
    signal.signal(signal.SIGTERM,lambda *_:rclpy.try_shutdown())
    try:rclpy.spin(node)
    except (KeyboardInterrupt,ExternalShutdownException):pass
    finally:node.destroy_node();rclpy.try_shutdown()

if __name__=='__main__':main()
