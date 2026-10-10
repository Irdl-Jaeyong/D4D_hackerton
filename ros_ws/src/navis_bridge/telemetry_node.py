#!/usr/bin/env python3
"""ROS odometry/image -> local web backend. No control publisher."""
import base64
import json
import math
import os
import time
from pathlib import Path
import urllib.request

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image

class Bridge(Node):
    def __init__(self):
        group = int(os.environ.get('NAVIS_BRIDGE_GROUP','0'))
        super().__init__(f'navis_telemetry_{group}')
        self.odoms = {}
        self.images = {}
        self.camera_mode = "wide"
        self.camera_checked = 0
        self.camera_revision = 0
        self.camera_target = 'UAV-01'
        self.camera_ready_sim_time = None
        self.odom_at = {}
        self.measured_speeds = {}
        self.image_at = 0
        self.sent_image_at = 0
        self.last_error = 0
        self.subscriptions_kept = []
        config = Path(os.environ.get('NAVIS_FLEET_CONFIG', str(Path(__file__).resolve().parents[3]/'config/fleet.json')))
        if not config.exists():
            from ament_index_python.packages import get_package_share_directory
            config = Path(get_package_share_directory('navis_sim'))/'config/fleet.json'
        fleet = json.loads(config.read_text())
        self.camera_vehicle = fleet['camera_vehicle']
        vehicles = [f'{kind}-{i:02}' for kind,key in [('SHIP','ships'),('UAV','uavs'),('USV','usvs')] for i in range(1,fleet[key]+1)]
        for vehicle in vehicles[group*13:(group+1)*13]:
            self.subscriptions_kept.append(self.create_subscription(Odometry, f'/navis/{vehicle.replace(chr(45),chr(95))}/odometry', lambda msg, vehicle=vehicle: self.on_odom(vehicle,msg), 10))
        if self.camera_vehicle in vehicles[group*13:(group+1)*13]:
            for mode in ('wide','detail','inspect'):
                self.subscriptions_kept.append(self.create_subscription(Image, '/navis/camera/'+mode, lambda msg, mode=mode: self.on_image(mode,msg), qos_profile_sensor_data))
        self.create_timer(0.2, self.send)
    def on_odom(self, vehicle, msg):
        old = self.odoms.get(vehicle)
        if old is not None:
            dt = (msg.header.stamp.sec-old.header.stamp.sec)+(msg.header.stamp.nanosec-old.header.stamp.nanosec)/1e9
            if dt > 0:
                p, previous = msg.pose.pose.position, old.pose.pose.position
                self.measured_speeds[vehicle] = math.sqrt((p.x-previous.x)**2+(p.y-previous.y)**2+(p.z-previous.z)**2)/dt
        self.odoms[vehicle] = msg
        self.odom_at[vehicle] = time.monotonic()
    def on_image(self, mode, msg):
        self.images[mode] = (msg,time.monotonic())
    def send(self):
        for vehicle in list(self.odoms):
            if time.monotonic()-self.odom_at[vehicle] < 2:
                self.send_vehicle(vehicle)
    def send_vehicle(self, vehicle):
        m = self.odoms[vehicle]
        p, q = m.pose.pose.position, m.pose.pose.orientation
        v = m.twist.twist.linear
        payload = {'vehicle_id':vehicle,'x':p.x,'y':p.y,'z':p.z,'yaw':math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),'roll':math.atan2(2*(q.w*q.x+q.y*q.z),1-2*(q.x*q.x+q.y*q.y)),'pitch':math.asin(max(-1,min(1,2*(q.w*q.y-q.z*q.x)))),'speed':self.measured_speeds.get(vehicle,0), 'speed_source':'odometry_position_delta','sim_time':m.header.stamp.sec+m.header.stamp.nanosec/1e9}
        now = time.monotonic()
        if vehicle == self.camera_vehicle and now-self.camera_checked >= .5:
            self.camera_checked=now
            try:
                with urllib.request.urlopen(os.environ.get('NAVIS_BACKEND_URL','http://127.0.0.1:18082')+'/api/camera/view',timeout=.2) as response:
                    view=json.load(response)
                    if (view['mode'],view['vehicle_id'],view.get('revision',0))!=(self.camera_mode,self.camera_target,self.camera_revision):
                        self.camera_mode=view['mode'];self.camera_target=view['vehicle_id'];self.camera_revision=view.get('revision',0)
                        self.images.pop(self.camera_mode,None)
                    self.camera_ready_sim_time=view.get('ready_sim_time')
            except (OSError,ValueError,KeyError):pass
        img,image_at=self.images.get(self.camera_mode,(None,0))
        capture_stamp=img.header.stamp.sec+img.header.stamp.nanosec/1e9 if img is not None else None
        ready=self.camera_mode!='inspect' or (self.camera_ready_sim_time is not None and capture_stamp is not None and capture_stamp>self.camera_ready_sim_time)
        if vehicle == self.camera_vehicle and img is not None and ready and now-image_at < 2 and now-self.sent_image_at >= .2:
            channels = 3 if img.encoding in ('rgb8','bgr8') else 0
            if channels:
                array = np.frombuffer(img.data,dtype=np.uint8).reshape(img.height,img.step)[:,:img.width*channels].reshape(img.height,img.width,channels)
                if img.encoding == 'rgb8': array = cv2.cvtColor(array,cv2.COLOR_RGB2BGR)
                ok, encoded = cv2.imencode('.jpg', array, [cv2.IMWRITE_JPEG_QUALITY,92])
                if ok: payload.update(camera_jpeg=base64.b64encode(encoded).decode(),camera_mode=self.camera_mode,camera_vehicle_id=self.camera_target,camera_revision=self.camera_revision,camera_capture_sim_time=capture_stamp)
        req = urllib.request.Request(os.environ.get('NAVIS_BACKEND_URL','http://127.0.0.1:18082')+'/api/internal/telemetry',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Bridge-Token':os.environ['NAVIS_BRIDGE_TOKEN']})
        try:
            with urllib.request.urlopen(req, timeout=1) as response: response.read()
            if 'camera_jpeg' in payload: self.sent_image_at=now
        except Exception as error:
            if now-self.last_error>5:
                self.get_logger().warning(str(error)); self.last_error=now

rclpy.init()
node = Bridge()
try: rclpy.spin(node)
except (KeyboardInterrupt, ExternalShutdownException): pass
finally:
    node.destroy_node()
    if rclpy.ok(): rclpy.shutdown()
