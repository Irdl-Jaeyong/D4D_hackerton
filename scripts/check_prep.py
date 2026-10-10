#!/usr/bin/env python3
"""Live HTTP checks for a running preparation stack; no simulation mutations."""
import json
import urllib.error
import urllib.request
from pathlib import Path
BASE = 'http://127.0.0.1:8000'
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=5) as r:return r.status,r.read()
def post(path,payload,headers=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=180) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
results=[]
def check(name,condition):
    if not condition:raise AssertionError(name)
    results.append(name); print('PASS',name,flush=True)
check('web entry',get('/')[0]==200)
check('frontend JS',get('/app.js')[0]==200)
state=json.loads(get('/api/state')[1])
fleet=json.loads((Path(__file__).resolve().parents[1]/'config/fleet.json').read_text())
check('all fleet vehicles live',len(state['vehicles'])==sum(fleet[k] for k in ('ships','uavs','usvs')) and all(v['connected'] for v in state['vehicles']))
check('camera is JPEG',get('/api/camera')[1].startswith(b'\xff\xd8'))
check('camera views available',json.loads(get('/api/camera/view')[1])['mode'] in ['wide','detail'])
check('internal telemetry rejects missing token',post('/api/internal/telemetry',{'x':0,'y':0,'yaw':0,'speed':0,'sim_time':0})[0]==403)
check('empty chat rejected',post('/api/chat',{'message':''})[0]==422)
responses=[]
for message,use_camera in ([('현재 연결 기체와 미연결 기체를 모두 나열해줘.',False),('현재 카메라에 보이는 물체의 색과 위치를 짧게 설명해줘.',True),('USV-01을 앞으로 이동시켜.',False)] if json.loads(get('/api/health')[1])['model_installed'] else []):
    status,response=post('/api/chat',{'message':message,'use_camera':use_camera})
    check('chat HTTP '+message,status==200 and response['executed'] is False and bool(response['reply']))
    responses.append({'message':message,'result':response})
    print(json.dumps(response,ensure_ascii=False),flush=True)
Path('outputs').mkdir(exist_ok=True)
Path('outputs/prep_checks.json').write_text(json.dumps({'checks':results,'responses':responses},ensure_ascii=False,indent=2))
