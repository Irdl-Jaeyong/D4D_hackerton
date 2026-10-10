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
from scenario_scene import targets as scene_targets
from app.approval_risk import evaluate, sort_key, CONFIG as RISK_CONFIG
missions={}
mission=None
mission_counter=0
formation={'usv':'circle','uav':'hemisphere','revision':0}
formation_status={}
app = FastAPI(title='NAVIS-AI preparation MVP')
latest = {}
battery_origin = {}
simulated_faults=set()
FAULT_TYPES=json.loads((ROOT/'config/fault_types.json').read_text())
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

def fault_modes():
    result={id:'propulsion' for id in simulated_faults}
    order={'payload':0,'communication':1,'propulsion':2}
    for m in missions.values():
        if m.get('scenario')=='fault':
            id=m['vehicle_id'];kind=m.get('fault_type','propulsion')
            if id not in result or order[kind]>order[result[id]]:result[id]=kind
    return result

def effective_faults():
    return simulated_faults | {m['vehicle_id'] for m in missions.values() if m.get('scenario')=='fault' and m.get('vehicle_id')}

def state():
    now = time.time()
    vehicles = []
    for id in IDS:
        value = latest.get(id)
        age = now - value['received_at'] if value else None
        vehicles.append({'id': id, 'type': id.split('-')[0], 'connected': age is not None and age < 5, 'age_seconds': age, 'source': 'gazebo_ros' if value else None, 'telemetry': value})
    for v in vehicles:
        v['readiness']=readiness(v,max(0,(v['telemetry'] or {}).get('sim_time',0)-battery_origin.get(v['id'],0)))
        kind=fault_modes().get(v['id'])
        if kind:
            v['fault_type']=kind
            v['readiness']['fault_behavior']=FAULT_TYPES[kind]['uav_behavior' if v['type']=='UAV' else 'usv_behavior']
        if v['id'] in effective_faults():
            v['readiness'].update(available=False,reason='수행불가 시연 주입' if v['id'] in simulated_faults else '고장 상황 자동 반영',operational_state='unavailable')
        if kind=='communication':
            event=next((m for m in missions.values() if m.get('vehicle_id')==v['id'] and m.get('fault_type')==kind),None)
            v['simulation_pose']=v['telemetry']
            v.update(telemetry=event.get('last_known') if event else None,connected=False,source='last_known',communication_status='두절 시연 · 마지막 관측 / 실제 상태 확인 불가')
        if mission and mission.get('approved'):
            task=next((t for t in mission['approved']['tasks'] if t['vehicle']==v['id']),None)
            if task:
                v['readiness']['task']=task['task']+' · 계획만 등록'
                v['readiness']['available']=False
                if v['readiness']['operational_state']!='unavailable':
                    v['readiness']['operational_state']='waiting'
                    v['readiness']['reason']='출동 미연결 · 승인 계획 대기'
    leader=next((v['telemetry'] for v in vehicles if v['id']=='SHIP-01' and v['connected']),None)
    sim_time=leader.get('sim_time') if leader else None
    for item in missions.values():
        if leader:
            if not item.get('scene_origin') or sim_time<item.get('scene_last_time',sim_time):item['scene_origin']={k:leader.get(k,0) for k in ('x','y','yaw','sim_time')}
            item['scene_last_time']=sim_time
    pending=[]
    for item in missions.values():
        item['risk']=evaluate(item['risk_signals'])
        if not item.get('approved'):pending.append(item)
    pending.sort(key=sort_key)
    return {'approval_queue':pending,'active_mission':mission if mission and mission.get('approved') else None,'mission':mission or (pending[0] if pending else None),'scenario_catalog':SCENARIOS,'vehicles': vehicles, 'camera_available': camera is not None and now-camera['received_at'] < 5, 'model': MODEL, 'camera_source': 'SHIP-01 stabilized overhead sensors', 'scene_mode': FLEET['motion']['uav_pattern'], 'camera_view':camera_view, 'formations': {**formation, 'catalog':CATALOG,'status':formation_status}, 'scene': {'camera':CAMERA_VIEWS[camera_view], 'motion':FLEET['motion'], 'scenario': None, 'sim_time':sim_time,'situations':scene_targets(missions.values(),sim_time)}}

class FormationRequest(BaseModel):
    group: Literal['usv','uav']
    mode: str
@app.get('/api/formations')
async def get_formations():
    return {**formation,'catalog':CATALOG,'status':formation_status,'simulated_faults':sorted(effective_faults()),'fault_modes':fault_modes()}
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
    scenario: Literal['crossing','debris','rescue','fault']
    vehicle_id: str | None = None
    fault_type: Literal['payload','propulsion','communication'] = 'propulsion'
class ApprovalRequest(BaseModel):
    mission_id: int
    option_id: Literal['observe','verify','prepare']
    plan_revision: int = Field(default=0,ge=0)
    human_confirmed: bool = False
    decision_source: Literal['captain_button','captain_text'] = 'captain_button'
    operator_command: str = Field(default='',max_length=100)

@app.post('/api/mission/scenario')
async def start_scenario(data: ScenarioRequest):
    global mission,mission_counter
    if len(missions)>=200:raise HTTPException(409,'대기열이 가득 찼습니다. 상황을 종료하세요.')
    if data.scenario=='fault' and (data.vehicle_id not in IDS or data.vehicle_id.startswith('SHIP')):raise HTTPException(422,'고장 대상 UAV 또는 USV를 지정하세요.')
    snapshot=state();plans=options(snapshot['vehicles'],formation,data.scenario)
    mission_counter+=1
    item={'id':mission_counter,'scenario':data.scenario,'card':SCENARIOS[data.scenario],
             'created_at':time.time(),'planned_at':time.time(),'plan_revision':0,'basis_revision':formation['revision'],'options':plans,'approved':None,'source':'synthetic',
             'execution_scope':'승인 시 대형만 Gazebo에 적용됩니다. 관측·확인 임무는 계획 등록이며 기체 출동은 연결되지 않았습니다.'}
    leader=next((v['telemetry'] for v in snapshot['vehicles'] if v['id']=='SHIP-01' and v['connected']),None)
    item['scene_origin']={k:leader.get(k,0) for k in ('x','y','yaw','sim_time')} if leader else None
    used={m.get('scene_slot',0) for m in missions.values() if m['scenario']==data.scenario}
    item['scene_slot']=next(i for i in range(201) if i not in used)
    if data.scenario=='fault':
        item['vehicle_id']=data.vehicle_id
        item['fault_type']=data.fault_type
        item['last_known']=dict(latest.get(data.vehicle_id,{}))
        fault=FAULT_TYPES[data.fault_type]
        item['card']={**item['card'],'title':data.vehicle_id+' '+fault['label'],'summary':fault['uav_behavior'] if data.vehicle_id.startswith('UAV') else fault['usv_behavior']}
    item['risk_signals']=dict(RISK_CONFIG['scenarios'].get(data.scenario,{}))
    if data.scenario=='fault':item['risk_signals']={k:FAULT_TYPES[data.fault_type][k] for k in ('S','U','A')}
    item['risk']=evaluate(item['risk_signals'])
    target=scene_targets([item],leader.get('sim_time') if leader else None)
    if target:item['options']=options(snapshot['vehicles'],formation,data.scenario,(target[0]['x'],target[0]['y']))
    missions[item['id']]=item
    if data.scenario=='fault':item['options']=options(state()['vehicles'],formation,data.scenario)
    return item

@app.post('/api/mission/{mission_id}/refresh')
async def refresh_plan(mission_id: int):
    item=missions.get(mission_id)
    if not item:raise HTTPException(404,'상황을 찾을 수 없습니다.')
    if item.get('approved'):raise HTTPException(409,'승인된 계획은 재계산할 수 없습니다.')
    snapshot=state();target=next((t for t in snapshot['scene']['situations'] if t['mission_id']==mission_id),None)
    item.update(options=options(snapshot['vehicles'],formation,item['scenario'],(target['x'],target['y']) if target else None),basis_revision=formation['revision'],planned_at=time.time(),plan_revision=item['plan_revision']+1)
    return item

class RiskSignals(BaseModel):
    S: float | None = Field(default=None,ge=0,le=5,allow_inf_nan=False)
    U: float | None = Field(default=None,ge=0,le=5,allow_inf_nan=False)
    A: float | None = Field(default=None,ge=0,le=5,allow_inf_nan=False)
    collision_imminent: bool = False
    severe_control_loss: bool = False
    reason: str = Field(default='시뮬레이션 위험도 입력',max_length=500)

@app.post('/api/mission/{mission_id}/assessment')
async def update_assessment(mission_id: int,data: RiskSignals,x_bridge_token: str=Header(default='')):
    if not TOKEN or not hmac.compare_digest(TOKEN,x_bridge_token):raise HTTPException(403,'Bridge token required')
    item=missions.get(mission_id)
    if not item:raise HTTPException(404,'상황을 찾을 수 없습니다.')
    if item.get('approved'):raise HTTPException(409,'승인 기록의 위험도는 변경할 수 없습니다.')
    item['risk_signals']=data.model_dump()
    item['risk']=evaluate(item['risk_signals'])
    return item

@app.post('/api/mission/approve')
async def approve_plan(data: ApprovalRequest):
    if not data.human_confirmed:raise HTTPException(409,'운용자의 명시적 최종 승인이 필요합니다.')
    global mission
    item=missions.get(data.mission_id)
    if not item:raise HTTPException(409,'상황을 찾을 수 없습니다.')
    if mission and mission.get('approved'):raise HTTPException(409,'진행 중인 승인 계획을 먼저 종료하세요.')
    if item.get('approved'):raise HTTPException(409,'이미 승인된 대응안입니다.')
    if data.plan_revision!=item['plan_revision']:raise HTTPException(409,'대응안이 재계산되었습니다. 새 대응안을 다시 선택하세요.')
    if time.time()-item['planned_at']>60:raise HTTPException(409,'추천이 60초 이상 지났습니다. 최신 상태로 다시 계산하세요.')
    plan=next((p for p in item['options'] if p['id']==data.option_id),None)
    if not plan or not plan['available']:raise HTTPException(409,'가용 기체가 부족합니다.')
    if data.decision_source=='captain_text':
        import re
        match=re.fullmatch(r'\s*([123])\s*번\s*(?:최종\s*)?승인\s*',data.operator_command)
        if not match or int(match[1])!=item['options'].index(plan)+1:raise HTTPException(422,'선택안과 일치하는 1번 승인 / 2번 승인 / 3번 승인을 입력하세요.')
    if formation['revision']!=item['basis_revision']:raise HTTPException(409,'대형이 변경되었습니다. 대응안을 다시 계산하세요.')
    current={v['id']:v for v in state()['vehicles']}
    if not any(v['type']=='SHIP' and v['connected'] for v in current.values()):raise HTTPException(409,'함선의 최신 상태가 없습니다. 다시 확인하세요.')
    for task in plan['tasks']:
        v=current[task['vehicle']]
        if not v['readiness']['available']:raise HTTPException(409,'기체 가용 상태가 변경되었습니다. 다시 계산하세요.')
        eta=task['eta_seconds']
        if v['readiness']['endurance_minutes']*60<2*eta+300:raise HTTPException(409,'복귀 여유가 부족합니다. 다시 계산하세요.')
    for group,mode in plan['formations'].items():
        if formation[group]!=mode:formation[group]=mode;formation['revision']+=1
    item['approved']={**plan,'approved_at':time.time(),'formation_revision':formation['revision'],'decision_source':data.decision_source,'operator_command':data.operator_command,'human_confirmed':True}
    mission=item
    return item

class CancelRequest(BaseModel):
    mission_id: int | None = None

@app.post('/api/mission/cancel')
async def cancel_plan(data: CancelRequest = CancelRequest()):
    global mission
    target=data.mission_id if data.mission_id is not None else mission['id'] if mission else None
    if target is None:raise HTTPException(422,'종료할 상황을 선택하세요.')
    if target not in missions:raise HTTPException(404,'상황을 찾을 수 없습니다.')
    del missions[target]
    if mission and mission['id']==target:mission=None
    return {'ok':True,'message':'선택 상황 종료. 다른 대기 상황과 현재 대형은 유지됩니다.'}

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

app.mount('/', StaticFiles(directory=ROOT/'frontend', html=True), name='frontend')
