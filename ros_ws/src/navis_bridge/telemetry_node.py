#!/usr/bin/env python3
"""ROS odometry/image -> local web backend. No control publisher."""
import base64
import json
import math
import os
import time
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
        super().__init__('navis_telemetry')
        self.odoms = {}
        self.image = None
        self.odom_at = {}
        self.image_at = 0
        self.sent_image_at = 0
        self.last_error = 0
        for vehicle in ['UAV-01','UAV-02','UAV-03','UAV-04','USV-01','USV-02']:
            self.create_subscription(Odometry, f'/navis/{vehicle.replace(chr(45),chr(95))}/odometry', lambda msg, vehicle=vehicle: self.on_odom(vehicle,msg), 10)
        self.create_subscription(Image, '/navis/camera', self.on_image, qos_profile_sensor_data)
        self.create_timer(0.2, self.send)
    def on_odom(self, vehicle, msg):
        self.odoms[vehicle] = msg
        self.odom_at[vehicle] = time.monotonic()
    def on_image(self, msg):
        self.image = msg
        self.image_at = time.monotonic()
    def send(self):
        for vehicle in list(self.odoms):
            if time.monotonic()-self.odom_at[vehicle] < 2:
                self.send_vehicle(vehicle)
    def send_vehicle(self, vehicle):
        m = self.odoms[vehicle]
        p, q = m.pose.pose.position, m.pose.pose.orientation
        v = m.twist.twist.linear
        payload = {'vehicle_id':vehicle,'x':p.x,'y':p.y,'z':p.z,'yaw':math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),'speed':math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z),'sim_time':m.header.stamp.sec+m.header.stamp.nanosec/1e9}
        now = time.monotonic()
        if vehicle == 'USV-01' and self.image is not None and now-self.image_at < 2 and now-self.sent_image_at >= 1:
            img = self.image
            channels = 3 if img.encoding in ('rgb8','bgr8') else 0
            if channels:
                array = np.frombuffer(img.data,dtype=np.uint8).reshape(img.height,img.step)[:,:img.width*channels].reshape(img.height,img.width,channels)
                if img.encoding == 'rgb8': array = cv2.cvtColor(array,cv2.COLOR_RGB2BGR)
                ok, encoded = cv2.imencode('.jpg', array, [cv2.IMWRITE_JPEG_QUALITY,85])
                if ok: payload['camera_jpeg'] = base64.b64encode(encoded).decode()
        req = urllib.request.Request(os.environ.get('NAVIS_BACKEND_URL','http://127.0.0.1:8000')+'/api/internal/telemetry',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Bridge-Token':os.environ['NAVIS_BRIDGE_TOKEN']})
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
