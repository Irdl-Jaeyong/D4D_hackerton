#!/usr/bin/env python3
"""Reconcile backend situation objects with Gazebo. Simulation time drives motion."""
import json,os,time,urllib.request,subprocess,re
from gazebo_status_bridge import service
from scenario_scene import model_sdf
os.environ.setdefault('IGN_PARTITION','navis-d4d')
BACKEND_URL = os.environ.get('NAVIS_BACKEND_URL','http://127.0.0.1:18082').rstrip('/')

class SceneBridge:
    def __init__(self):self.known={};self.last_clock=None
    def sync(self,snapshot):
        clock=snapshot.get('scene',{}).get('sim_time')
        if clock is not None and self.last_clock is not None and clock<self.last_clock:self.known.clear()
        if clock is not None:self.last_clock=clock
        wanted={t['name']:t for t in snapshot['scene'].get('situations',[])}
        for name in list(self.known):
            if name not in wanted or self.known[name]!=(wanted[name]['scenario'],wanted[name]['priority']):
                if service('/world/navis_prep/remove','ignition.msgs.Entity',f'name: {json.dumps(name)} type: MODEL'):del self.known[name]
        for name,t in wanted.items():
            if name not in self.known:
                if service('/world/navis_prep/create','ignition.msgs.EntityFactory','sdf: '+json.dumps(model_sdf(t))+' allow_renaming: false'):self.known[name]=(t['scenario'],t['priority'])
                else:service('/world/navis_prep/remove','ignition.msgs.Entity',f'name: {json.dumps(name)} type: MODEL')
        poses=[]
        for name,t in wanted.items():
            if name in self.known:
                import math
                roll,pitch,yaw=(t.get('roll',0)/2,t.get('pitch',0)/2,t['yaw']/2);cr,sr=math.cos(roll),math.sin(roll);cp,sp=math.cos(pitch),math.sin(pitch);cy,sy=math.cos(yaw),math.sin(yaw)
                q=(cr*cp*cy+sr*sp*sy,sr*cp*cy-cr*sp*sy,cr*sp*cy+sr*cp*sy,cr*cp*sy-sr*sp*cy)
                poses.append('pose {name: %s position {x:%s y:%s z:%s} orientation {w:%s x:%s y:%s z:%s}}' % (json.dumps(name),t['x'],t['y'],t['z'],*q))
        if poses:service('/world/navis_prep/set_pose_vector','ignition.msgs.Pose_V',' '.join(poses))

if __name__=='__main__':
    bridge=SceneBridge()
    # Reconcile existing objects, including ones left after a backend restart.
    try:
        p=subprocess.run(['ign','service','-s','/world/navis_prep/scene/info','--reqtype','ignition.msgs.Empty','--reptype','ignition.msgs.Scene','--timeout','3000','--req',''],capture_output=True,text=True,timeout=4)
        for name in set(re.findall(r'name: "(situation_[0-9]+(?:_[0-9]+)?)"',p.stdout)):
            bridge.known[name]=('old',None)
    except subprocess.TimeoutExpired:pass
    while True:
        try:
            with urllib.request.urlopen(BACKEND_URL+'/api/state',timeout=1) as response:bridge.sync(json.load(response))
        except Exception as e:print('Scenario scene retry:',type(e).__name__,flush=True)
        time.sleep(.25)
