import asyncio
import base64
import hmac
import json
import os
import time
import sys
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from formation_motion import CATALOG
from mission_console import readiness, options, SCENARIOS
mission=None
mission_counter=0
formation={'usv':'circle','uav':'hemisphere','revision':0}
formation_status={}
app = FastAPI(title='NAVIS-AI preparation MVP')
latest = {}
battery_origin = {}
simulated_faults=set()
camera = None
lock = asyncio.Lock()
chat_lock = asyncio.Lock()
TOKEN = os.environ.get('NAVIS_BRIDGE_TOKEN', '')
MODEL = os.environ.get('OLLAMA_MODEL', 'minicpm-v4.5:latest')
OLLAMA = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
FLEET = json.loads((ROOT/'config/fleet.json').read_text())
IDS = [f'{kind}-{i:02}' for kind, key in [('SHIP','ships'),('UAV','uavs'),('USV','usvs')] for i in range(1, FLEET[key]+1)]
CAMERA_VEHICLE = FLEET['camera_vehicle']
camera_view = 'wide'
CAMERA_VIEWS = FLEET.get('camera_views', {'wide':FLEET['camera']})

class CameraView(BaseModel):
    mode: Literal['wide','detail']

class Telemetry(BaseModel):
    vehicle_id: str = 'USV-01'
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    z: float = Field(default=0, allow_inf_nan=False)
    yaw: float = Field(allow_inf_nan=False)
    speed: float = Field(ge=0, allow_inf_nan=False)
    sim_time: float = Field(ge=0, allow_inf_nan=False)
    speed_source: Literal['ros_twist','odometry_position_delta'] = 'ros_twist'
    camera_jpeg: str | None = Field(default=None, max_length=2_000_000)

class Turn(BaseModel):
    role: str
    content: str = Field(max_length=4000)

class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    use_camera: bool = False
    history: list[Turn] = Field(default_factory=list, max_length=8)

def state():
    now = time.time()
    vehicles = []
    for id in IDS:
        value = latest.get(id)
        age = now - value['received_at'] if value else None
        vehicles.append({'id': id, 'type': id.split('-')[0], 'connected': age is not None and age < 5, 'age_seconds': age, 'source': 'gazebo_ros' if value else None, 'telemetry': value})
    for v in vehicles:
        v['readiness']=readiness(v,max(0,(v['telemetry'] or {}).get('sim_time',0)-battery_origin.get(v['id'],0)))
        if v['id'] in simulated_faults:
            v['readiness'].update(available=False,reason='수행불가 시연 주입',operational_state='unavailable')
        if mission and mission.get('approved'):
            task=next((t for t in mission['approved']['tasks'] if t['vehicle']==v['id']),None)
            if task:
                v['readiness']['task']=task['task']+' · 계획만 등록'
                v['readiness']['available']=False
                execution=mission.get('execution',{}).get('tasks',{}).get(v['id'])
                if execution:
                    labels={'outbound':'출동 중','observing':'관측 중','returning':'복귀 중','completed':'완료 · 대형 유지'}
                    v['readiness']['task']=task['task']+' · '+labels.get(execution['stage'],'확인 필요')
                    if execution.get('blocked'):v['readiness'].update(operational_state='unavailable',reason='임무 중 상태 확인 필요')
                    elif v['readiness']['operational_state']!='unavailable':
                        v['readiness']['operational_state']='waiting' if execution['stage']=='completed' else 'defending'
                        v['readiness']['reason']='실측 위치 기반 임무 진행'
                if not execution and v['readiness']['operational_state']!='unavailable':
                    v['readiness']['operational_state']='waiting'
                    v['readiness']['reason']='출동 미연결 · 승인 계획 대기'
    return {'mission':mission,'scenario_catalog':SCENARIOS,'vehicles': vehicles, 'camera_available': camera is not None and now-camera['received_at'] < 5, 'model': MODEL, 'camera_source': 'SHIP-01 stabilized overhead sensors', 'scene_mode': FLEET['motion']['uav_pattern'], 'camera_view':camera_view, 'formations': {**formation, 'catalog':CATALOG,'status':formation_status}, 'scene': {'camera':CAMERA_VIEWS[camera_view], 'motion':FLEET['motion'], 'scenario': None}}

class FormationRequest(BaseModel):
    group: Literal['usv','uav']
    mode: str
@app.get('/api/formations')
async def get_formations():
    return {**formation,'catalog':CATALOG,'status':formation_status,'mission':mission,'availability':{v['id']:v['connected'] and v['id'] not in simulated_faults and (v['type']=='SHIP' or v['readiness']['battery_percent']>=35) for v in state()['vehicles']}}
@app.post('/api/formations')
async def set_formation(data: FormationRequest):
    if mission and mission.get('approved'):raise HTTPException(409,'승인된 대응안을 종료한 뒤 대형을 변경하세요.')
    if data.mode not in CATALOG[data.group]:raise HTTPException(422,'Unknown formation')
    if formation[data.group]!=data.mode:
        formation[data.group]=data.mode;formation['revision']+=1
    return await get_formations()
@app.post('/api/internal/formations')
async def report_formations(data: dict,x_bridge_token: str=Header(default='')):
    global formation_status
    if not TOKEN or not hmac.compare_digest(TOKEN,x_bridge_token):raise HTTPException(403,'Bridge token required')
    formation_status=data
    return {'ok':True}


class ScenarioRequest(BaseModel):
    scenario: Literal['crossing','debris','rescue']
class ApprovalRequest(BaseModel):
    mission_id: int
    option_id: Literal['observe','verify','prepare']
    human_confirmed: bool = False
    decision_source: Literal['captain_button','captain_text'] = 'captain_button'
    operator_command: str = Field(default='',max_length=100)

@app.post('/api/mission/scenario')
async def start_scenario(data: ScenarioRequest):
    global mission,mission_counter
    if mission and mission.get('approved'):raise HTTPException(409,'진행 중인 대응안을 먼저 종료하세요.')
    snapshot=state();plans=options(snapshot['vehicles'],formation,data.scenario)
    mission_counter+=1
    mission={'id':mission_counter,'scenario':data.scenario,'card':SCENARIOS[data.scenario],
             'created_at':time.time(),'basis_revision':formation['revision'],'options':plans,'approved':None,'source':'synthetic',
             'execution_scope':'승인 시 대형과 UAV 관측·복귀를 실행합니다. USV 확인 출동은 계획 등록입니다.'}
    return mission

@app.post('/api/mission/approve')
async def approve_plan(data: ApprovalRequest):
    if not data.human_confirmed:raise HTTPException(409,'운용자의 명시적 최종 승인이 필요합니다.')
    if not mission or mission['id']!=data.mission_id:raise HTTPException(409,'상황 카드가 변경되었습니다.')
    if mission.get('approved'):raise HTTPException(409,'이미 승인된 대응안입니다.')
    if time.time()-mission['created_at']>60:raise HTTPException(409,'추천이 60초 이상 지났습니다. 최신 상태로 다시 계산하세요.')
    plan=next((p for p in mission['options'] if p['id']==data.option_id),None)
    if not plan or not plan['available']:raise HTTPException(409,'가용 기체가 부족합니다.')
    if data.decision_source=='captain_text':
        import re
        match=re.fullmatch(r'\s*([123])\s*번\s*(?:최종\s*)?승인\s*',data.operator_command)
        if not match or int(match[1])!=mission['options'].index(plan)+1:raise HTTPException(422,'선택안과 일치하는 1번 승인 / 2번 승인 / 3번 승인을 입력하세요.')
    if formation['revision']!=mission['basis_revision']:raise HTTPException(409,'대형이 변경되었습니다. 대응안을 다시 계산하세요.')
    current={v['id']:v for v in state()['vehicles']}
    if not any(v['type']=='SHIP' and v['connected'] for v in current.values()):raise HTTPException(409,'함선의 최신 상태가 없습니다. 다시 확인하세요.')
    for task in plan['tasks']:
        v=current[task['vehicle']]
        if not v['readiness']['available']:raise HTTPException(409,'기체 가용 상태가 변경되었습니다. 다시 계산하세요.')
        eta=task['eta_seconds']
        if v['readiness']['endurance_minutes']*60<2*eta+300:raise HTTPException(409,'복귀 여유가 부족합니다. 다시 계산하세요.')
    for group,mode in plan['formations'].items():
        if formation[group]!=mode:formation[group]=mode;formation['revision']+=1
    mission['approved']={**plan,'approved_at':time.time(),'formation_revision':formation['revision'],'decision_source':data.decision_source,'operator_command':data.operator_command,'human_confirmed':True}
    mission['energy_at_start']={t['vehicle']:current[t['vehicle']]['readiness']['battery_percent'] for t in plan['tasks']}
    mission['execution']={'status':'pending','tasks':{}}
    return mission

@app.post('/api/mission/cancel')
async def cancel_plan():
    global mission
    if mission and mission.get('approved') and mission.get('execution',{}).get('status') not in ('completed','cancelled'):
        mission['cancel_requested']=True
        return {'ok':True,'message':'취소 요청 · 관측 UAV가 대형으로 복귀합니다.'}
    mission=None
    return {'ok':True,'message':'계획 종료. 현재 대형은 유지됩니다.'}

class ExecutionReport(BaseModel):
    mission_id: int
    sim_time: float = Field(ge=0,allow_inf_nan=False)
    elapsed_seconds: float = Field(ge=0,allow_inf_nan=False)
    tasks: dict
    status: Literal['running','completed','cancelled']
    cancelled: bool = False
@app.post('/api/internal/execution')
async def report_execution(data: ExecutionReport,x_bridge_token: str=Header(default='')):
    if not TOKEN or not hmac.compare_digest(TOKEN,x_bridge_token):raise HTTPException(403,'Bridge token required')
    if not mission or mission['id']!=data.mission_id or not mission.get('approved'):raise HTTPException(409,'Mission changed')
    previous=mission.get('execution',{})
    if previous.get('status') in ('completed','cancelled'):
        previous['received_at']=time.time()
        return {'ok':True}
    mission['execution']={**data.model_dump(),'received_at':time.time()}
    for id,task in mission['execution']['tasks'].items():
        current=latest.get(id)
        if current:
            remaining=readiness({'id':id,'type':'UAV','connected':True,'telemetry':current},max(0,current['sim_time']-battery_origin.get(id,0)))['battery_percent']
            task['simulated_battery_used']=round(max(0,mission['energy_at_start'].get(id,remaining)-remaining),1)
    return {'ok':True}

class FaultRequest(BaseModel):
    unavailable: bool
@app.post('/api/vehicles/{vehicle_id}/simulated-fault')
async def set_simulated_fault(vehicle_id: str,data: FaultRequest):
    if vehicle_id not in IDS or vehicle_id.startswith('SHIP'):raise HTTPException(422,'지원 기체를 선택하세요.')
    if data.unavailable:simulated_faults.add(vehicle_id)
    else:simulated_faults.discard(vehicle_id)
    return {'ok':True,'source':'simulated'}

@app.get('/api/health')
async def health():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(OLLAMA + '/api/tags'); r.raise_for_status()
        models = [m['name'] for m in r.json()['models']]
        return {'backend': 'ok', 'ollama': 'ok', 'model_installed': MODEL in models, 'model': MODEL}
    except (httpx.HTTPError, ValueError, KeyError):
        return {'backend': 'ok', 'ollama': 'unavailable', 'model_installed': False, 'model': MODEL}

@app.get('/api/state')
async def get_state():
    return state()

@app.get('/api/camera/view')
async def get_camera_view():
    return {'mode':camera_view, 'camera':CAMERA_VIEWS[camera_view]}

@app.post('/api/camera/view')
async def set_camera_view(data: CameraView):
    global camera_view
    if data.mode not in CAMERA_VIEWS:
        raise HTTPException(422, 'Camera view unavailable')
    camera_view = data.mode
    return {'mode':camera_view, 'camera':CAMERA_VIEWS[camera_view]}

@app.post('/api/internal/telemetry')
async def telemetry(data: Telemetry, x_bridge_token: str = Header(default='')):
    global camera
    if not TOKEN or not hmac.compare_digest(TOKEN, x_bridge_token):
        raise HTTPException(403, 'Bridge token required')
    if data.vehicle_id not in IDS:
        raise HTTPException(422, 'Unknown vehicle ID')
    raw = None
    if data.camera_jpeg and data.vehicle_id != CAMERA_VEHICLE:
        raise HTTPException(422, 'Only the designated fleet camera carrier is accepted')
    if data.camera_jpeg:
        try:
            raw = base64.b64decode(data.camera_jpeg, validate=True)
            if not raw.startswith(b'\xff\xd8'):
                raise ValueError('not jpeg')
        except ValueError:
            raise HTTPException(422, 'Invalid JPEG')
    async with lock:
        received = time.time()
        if data.vehicle_id not in battery_origin or data.sim_time<battery_origin[data.vehicle_id]:battery_origin[data.vehicle_id]=data.sim_time
        latest[data.vehicle_id] = {**data.model_dump(exclude={'camera_jpeg'}), 'received_at': received}
        if raw:
            camera = {'jpeg': raw, 'received_at': received}
    return {'ok': True}

@app.get('/api/camera')
async def get_camera():
    if not camera or time.time()-camera['received_at'] >= 5:
        raise HTTPException(503, 'No fresh camera image')
    return Response(camera['jpeg'], media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

@app.post('/api/chat')
async def chat(data: Chat):
    if chat_lock.locked():
        raise HTTPException(429, 'AI is processing another request')
    async with chat_lock:
        snapshot = state()
        msg = {'role': 'user', 'content': data.message}
        if data.use_camera:
            if not snapshot['camera_available']:
                raise HTTPException(409, 'No fresh camera image; start the simulation')
            msg['images'] = [base64.b64encode(camera['jpeg']).decode()]
        connected_ids = [v['id'] for v in snapshot['vehicles'] if v['connected']]
        offline_ids = [v['id'] for v in snapshot['vehicles'] if not v['connected']]
        system = ('당신은 NAVIS-AI 시뮬레이션 관제 보조입니다. 한국어로 짧고 명확하게 답하세요. '
                  '제공된 실제 상태만 사용하고 배터리, 위치, 연결상태를 추측하지 마세요. '
                  '카메라는 함대 전체를 비스듬히 내려다보는 Gazebo 항공 관측 카메라입니다. 메인 함선은 직선 전진하고 USV와 드론은 선택된 함선 상대 대형을 유지합니다. USV는 추진력 기반, 드론은 위치 갱신 기반 시연입니다. 배터리는 시뮬레이션 추정값입니다. 상황과 대응안은 규칙 기반 시연이며 관측 임무 출동은 미연결입니다. 보이는 것만 설명하고 불확실하면 명시하세요. '
                  '현재는 상태 조회와 이미지 설명만 가능하며 이동 명령 실행 기능은 없습니다. '
                  '명령을 실행했다고 주장하지 마세요. 상태가 없는 기체는 미연결입니다. '
                  '상태 요약에서 기체를 빠뜨리지 마세요. 연결 기체: '+', '.join(connected_ids)+
                  '. 미연결 기체: '+', '.join(offline_ids)+'. 현재 상태 JSON: '+json.dumps(snapshot, ensure_ascii=False))
        history = [{'role': t.role, 'content': t.content} for t in data.history if t.role in ('user','assistant')]
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(OLLAMA+'/api/chat', json={'model':MODEL,'messages':[{'role':'system','content':system}]+history+[msg], 'stream':False,'think':False,'options':{'temperature':0,'num_ctx':4096,'num_predict':384}})
                response.raise_for_status(); output = response.json()
                if 'error' in output:
                    raise ValueError(output['error'])
            return {'reply':output['message']['content'],'elapsed_seconds':round(time.perf_counter()-started,2),'used_camera':data.use_camera,'executed':False}
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise HTTPException(502, 'Model request failed: '+str(error))

# Preserve human-approved plans and completed results across backend restarts.
CONSOLE_SNAPSHOT=ROOT/'outputs'/'console_snapshot.json'
def restore_console():
    global mission,mission_counter
    try:
        saved=json.loads(CONSOLE_SNAPSHOT.read_text())
        if any(saved['formation'][g] not in CATALOG[g] for g in ('usv','uav')):return
        formation.update(saved['formation']);mission=saved.get('mission');mission_counter=saved.get('mission_counter',0)
        simulated_faults.update(id for id in saved.get('faults',[]) if id in IDS)
        battery_origin.update(saved.get('battery_origin',{}))
    except (OSError,ValueError,KeyError,TypeError):pass

def save_console():
    CONSOLE_SNAPSHOT.parent.mkdir(exist_ok=True)
    data={'formation':formation,'mission':mission,'mission_counter':mission_counter,'faults':list(simulated_faults),'battery_origin':battery_origin}
    temp=CONSOLE_SNAPSHOT.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(CONSOLE_SNAPSHOT)
app.add_event_handler('startup',restore_console)
app.add_event_handler('shutdown',save_console)

app.mount('/', StaticFiles(directory=ROOT/'frontend', html=True), name='frontend')
