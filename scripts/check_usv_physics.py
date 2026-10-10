import urllib.request,json,time,math
from pathlib import Path
rows=[]
previous_time=None;stable=0
for _ in range(80):
 s=json.load(urllib.request.urlopen('http://localhost:8000/api/state',timeout=3))
 stamp=next((v['telemetry']['sim_time'] for v in s['vehicles'] if v['id']=='SHIP-01' and v.get('telemetry')),0)
 stable=stable+1 if all(v['connected'] for v in s['vehicles']) and previous_time is not None and stamp>previous_time else 0
 previous_time=stamp
 if stable>=3:break
 time.sleep(1)
for _ in range(40):
 s=json.load(urllib.request.urlopen('http://localhost:8000/api/state',timeout=3))
 vehicles={v['id']:v for v in s['vehicles']};lead=vehicles['SHIP-01']['telemetry'];t=lead['x']/1.5
 boats=[];errors=[]
 for i in range(10):
  v=vehicles[f'USV-{i+1:02}'];p=v['telemetry'];a=2*math.pi*i/10+.007*t
  target=(lead['x']+115*math.cos(a),75*math.sin(a))
  error=math.hypot(p['x']-target[0],p['y']-target[1]);errors.append(error);boats.append(p)
  assert v['connected']
  assert .2<p['z']<1.2,(i,p)
  assert error<130,(i,error)
 spacing=min(math.hypot(a['x']-b['x'],a['y']-b['y']) for i,a in enumerate(boats) for b in boats[i+1:])
 assert spacing>10,spacing
 rows.append({'t':t,'errors':errors,'min_spacing':spacing,'boats':boats})
 time.sleep(1)
assert rows[-1]['t']>rows[0]['t']+5
assert max(rows[-1]['errors'])<130,rows[-1]['errors']
out=Path(__file__).resolve().parents[1]/'outputs'
out.mkdir(exist_ok=True)
(out/'usv_physics_check.json').write_text(json.dumps(rows,indent=2))
print('PASS: 10 force-driven escorts; max error',max(max(r['errors']) for r in rows),'final error',max(rows[-1]['errors']),'min spacing',min(r['min_spacing'] for r in rows),'forward metres',1.5*(rows[-1]['t']-rows[0]['t']))
