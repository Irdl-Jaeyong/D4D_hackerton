#!/usr/bin/env python3
"""Set the Gazebo native view to follow the same flagship as the web camera."""
import json,math,subprocess,time,urllib.request
from pathlib import Path
fleet=json.loads((Path(__file__).resolve().parents[1]/'config/fleet.json').read_text())
cam=fleet['camera']
def request(service,kind,payload):
    try:
        p=subprocess.run(['ign','service','-s',service,'--reqtype',kind,'--reptype','ignition.msgs.Boolean','--timeout','600','--req',payload],capture_output=True,text=True,timeout=1)
        return p.returncode==0 and 'true' in p.stdout
    except subprocess.TimeoutExpired:return False
for attempt in range(20):
    if request('/gui/follow','ignition.msgs.StringMsg','data:"SHIP-01"'):
        x,y,z=cam['offset']
        request('/gui/follow/offset','ignition.msgs.Vector3d',f'x:{x} y:{y} z:{z}')
        print('Gazebo camera follows SHIP-01 at a wide aerial offset',flush=True)
        break
    time.sleep(.25)
else:print('Gazebo GUI follow service was not available',flush=True)
