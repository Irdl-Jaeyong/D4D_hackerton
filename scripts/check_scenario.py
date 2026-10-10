"""Observe one live traffic encounter and recovery using real fleet telemetry."""
import os
import json,math,time,urllib.request
from pathlib import Path
base=os.environ.get('NAVIS_BACKEND_URL','http://127.0.0.1:18082').rstrip('/')
rows=[];stable=0;previous=0
for _ in range(90):
 state=json.load(urllib.request.urlopen(base+'/api/state',timeout=3))
 if not state.get('scene',{}).get('scenario'):raise SystemExit('Traffic scenario is disabled; formation selection is active.')
 lead=next(v for v in state['vehicles'] if v['id']=='SHIP-01')
 stamp=(lead.get('telemetry') or {}).get('sim_time',0)
 stable=stable+1 if stamp>previous and all(v['connected'] for v in state['vehicles']) else 0
 previous=stamp
 if stable>=3:break
 time.sleep(1)
start=time.monotonic()
while time.monotonic()-start<480:
 state=json.load(urllib.request.urlopen(base+'/api/state',timeout=3))
 vehicles={v['id']:v for v in state['vehicles']};lead=vehicles['SHIP-01']['telemetry'];t=lead['x']/1.5
 assert all(v['connected'] for v in state['vehicles'])
 civilian=(lead['x']+105,120-3*(t%180));errors=[];distances=[];boats=[]
 for i in range(10):
  p=vehicles[f'USV-{i+1:02}']['telemetry'];boats.append(p);a=2*math.pi*i/10+.007*t
  errors.append(math.hypot(p['x']-(lead['x']+115*math.cos(a)),p['y']-75*math.sin(a)))
  distances.append(math.hypot(p['x']-civilian[0],p['y']-civilian[1]))
  assert .15<p['z']<1.25,(i,p)
  ship_clearance=math.hypot(max(0,abs(p['x']-lead['x'])-80),max(0,abs(p['y'])-12))
  assert ship_clearance>4,(i,ship_clearance,t)
 spacing=min(math.hypot(a['x']-b['x'],a['y']-b['y']) for i,a in enumerate(boats) for b in boats[i+1:])
 rows.append({'t':t,'formation_error':max(errors),'civilian_distance':min(distances),'escort_spacing':spacing})
 if t>=170:break
 time.sleep(.75)
else:raise AssertionError('Scenario did not finish within 480 wall seconds')
out=Path(__file__).resolve().parents[1]/'outputs';out.mkdir(exist_ok=True)
(out/'scenario_check.json').write_text(json.dumps(rows,indent=2))
assert rows[0]['t']<15,'Run shortly after restarting simulation to capture approach'
assert max(r['formation_error'] for r in rows)>10,'No significant avoidance observed'
assert min(r['civilian_distance'] for r in rows)>10, min(r['civilian_distance'] for r in rows)
assert min(r['escort_spacing'] for r in rows)>10
assert rows[-1]['formation_error']<6,rows[-1]
print('PASS approach, avoidance, and recovery:',{'max_diversion_m':max(r['formation_error'] for r in rows),'civilian_clearance_m':min(r['civilian_distance'] for r in rows),'escort_spacing_m':min(r['escort_spacing'] for r in rows),'recovery_error_m':rows[-1]['formation_error']})
