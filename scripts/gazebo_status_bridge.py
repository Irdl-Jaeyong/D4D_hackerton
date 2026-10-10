#!/usr/bin/env python3
"""Native colored status indicators, shared by GUI and camera sensors.
No vehicle positions or controllers are modified. Runs inside the sim container.
"""
import json,math,time,subprocess,urllib.request,os
os.environ['IGN_PARTITION']='navis-d4d-koyul'
STATES={'defending':'.17 .88 .6 1','waiting':'.29 .66 1 1','unavailable':'1 .42 .42 1'}

def service(name,kind,request):
 r=subprocess.run(['ign','service','-s',name,'--reqtype',kind,'--reptype','ignition.msgs.Boolean','--timeout','700','--req',request],capture_output=True,text=True,timeout=1.2)
 return r.returncode==0 and 'true' in r.stdout

def create(vehicles):
 request=[]
 for v in vehicles:
  for state,color in STATES.items():
   name='status_dot_'+v['id']+'_'+state
   radius=.35 if v['id'].startswith('UAV') else 1.5
   sdf=f'''<sdf version="1.8"><model name="{name}"><static>true</static><pose>0 0 -200 0 0 0</pose><link name="label"><visual name="indicator"><pose>0 0 0 0 0 0</pose><geometry><sphere><radius>{radius}</radius></sphere></geometry><cast_shadows>false</cast_shadows><material><ambient>{color}</ambient><diffuse>{color}</diffuse><emissive>{color}</emissive></material></visual></link></model></sdf>'''
   request.append('data {sdf: '+json.dumps(sdf)+' allow_renaming: false}')
 for v in vehicles:
  if v['id'].startswith('UAV'):
   sdf=f'<sdf version="1.8"><model name="charge_pad_{v["id"]}"><static>true</static><pose>0 0 -200 0 0 0</pose><link name="pad"><visual name="charging"><geometry><cylinder><radius>1.1</radius><length>.04</length></cylinder></geometry><material><ambient>.1 1 .85 1</ambient><diffuse>.1 1 .85 1</diffuse><emissive>.1 1 .85 1</emissive></material></visual></link></model></sdf>'
   request.append('data {sdf: '+json.dumps(sdf)+' allow_renaming: false}')
 request.append('data {sdf: '+json.dumps('<sdf version="1.8"><model name="observation_target"><static>true</static><pose>0 0 -200 0 0 0</pose><link name="marker"><visual name="buoy"><geometry><sphere><radius>3</radius></sphere></geometry><material><ambient>1 .5 .05 1</ambient><diffuse>1 .5 .05 1</diffuse></material></visual></link></model></sdf>')+' allow_renaming: false}')
 results=[service('/world/navis_prep/create_multiple','ignition.msgs.EntityFactory_V',' '.join(request[i:i+15])) for i in range(0,len(request),15)]
 print('Status indicator creation:',sum(results),'/',len(results),flush=True)
 # Duplicate model names return false after a bridge restart. Pose updates
 # validate that the full set exists and retry creation on repeated failure.
 return True

def poses(snapshot,last_positions):
 camera=snapshot['scene']['camera'];roll=math.pi/2-camera['pitch'];yaw=camera['yaw']-math.pi/2
 # Colored spheres remain visible from both native GUI and sensor cameras.
 cr,sr=math.cos(roll/2),math.sin(roll/2);cy,sy=math.cos(yaw/2),math.sin(yaw/2)
 result=[]
 for v in snapshot['vehicles']:
  if v['connected'] and v['telemetry']:last_positions[v['id']]=v['telemetry']
  p=last_positions.get(v['id']);state=v['readiness']['operational_state']
  for key in STATES:
   active=key==state and p is not None and not (snapshot.get('camera_view')=='inspect' and snapshot.get('inspection_vehicle')==v['id'])
   offset=.2 if v.get('fault',{}).get('phase')=='charging' else .7 if v['id'].startswith('UAV') else 8
   x,y,z=(p['x'],p['y'],p.get('z',0)+offset) if active else (0,0,-200)
   result.append('pose {name: %s position {x:%s y:%s z:%s} orientation {w:%s x:%s y:%s z:%s}}' % (json.dumps('status_dot_'+v['id']+'_'+key),x,y,z,cr*cy,sr*cy,sr*sy,cr*sy))
  if v['id'].startswith('UAV'):
   charging=p is not None and v.get('fault',{}).get('phase')=='charging' and not (snapshot.get('camera_view')=='inspect' and snapshot.get('inspection_vehicle')==v['id'])
   x,y,z=(p['x'],p['y'],p['z']-.13) if charging else (0,0,-200)
   result.append('pose {name: %s position {x:%s y:%s z:%s}}'%(json.dumps('charge_pad_'+v['id']),x,y,z))
 execution=(snapshot.get('mission') or {}).get('execution',{})
 task=next(iter(execution.get('tasks',{}).values()),None)
 target=task.get('target_world') if task else None
 x,y,z=(target[0],target[1],1) if target else (0,0,-200)
 result.append('pose {name: "observation_target" position {x:%s y:%s z:%s}}'%(x,y,z))
 return ' '.join(result)

if __name__=='__main__':
 initialized=False;last_positions={};last_clock=None;failures=0
 while True:
  try:
   with urllib.request.urlopen('http://127.0.0.1:8000/api/state',timeout=.8) as response:s=json.load(response)
   lead=next((v for v in s['vehicles'] if v['type']=='SHIP' and v['connected']),None)
   stamp=lead['telemetry']['sim_time'] if lead else None
   if stamp is not None and last_clock is not None and stamp<last_clock:initialized=False
   if stamp is not None:last_clock=stamp
   if not initialized and lead:initialized=create(s['vehicles'])
   if initialized:
    if not service('/world/navis_prep/set_pose_vector','ignition.msgs.Pose_V',poses(s,last_positions)):failures+=1
    else:failures=0
    if failures>3:initialized=False
  except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):pass
  time.sleep(.5)
