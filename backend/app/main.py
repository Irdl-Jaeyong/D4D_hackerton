import asyncio
from contextlib import asynccontextmanager
import base64
import hmac
import math
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
from risk_monitor import assess
from fault_motion import deck_slot
from scenario_scene import targets as scene_targets
mission=None
mission_counter=0
formation={'usv':'circle','uav':'hemisphere','revision':0}
formation_status={}
@asynccontextmanager
async def console_lifespan(application):
    restore_console()
    try:
        yield
    finally:
        save_console()

app = FastAPI(title='NAVIS-AI preparation MVP', lifespan=console_lifespan)
latest = {}
battery_origin = {}
simulated_faults=set()
fault_status={}
fault_kinds={}
fault_last_known={}
FAULT_TYPES=json.loads((ROOT/"config/fault_types.json").read_text())
charge_credit={}
risk_cache={"evaluated_at":0,"items":[]}
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
inspection_vehicle='UAV-01'
CAMERA_VIEWS = FLEET.get('camera_views', {'wide':FLEET['camera']})

class CameraView(BaseModel):
    mode: Literal['wide','detail','inspect']
    vehicle_id: str | None = None

class Telemetry(BaseModel):
    vehicle_id: str = 'USV-01'
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)
    z: float = Field(default=0, allow_inf_nan=False)
    yaw: float = Field(allow_inf_nan=False)
    roll: float = Field(default=0, allow_inf_nan=False)
    pitch: float = Field(default=0, allow_inf_nan=False)
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
        credit=charge_credit.get(v['id'],0)
        if v['readiness']['battery_percent'] is not None and credit:
            v['readiness']['battery_percent']=round(min(100,v['readiness']['battery_percent']+credit),1)
            v['readiness']['endurance_minutes']=round(v['readiness']['battery_percent']/100*(35 if v['type']=='UAV' else 180),1)
        if v['type']=='UAV' and v['connected'] and (v['readiness']['battery_percent']<35 or max(abs((v['telemetry'] or {}).get('roll',0)),abs((v['telemetry'] or {}).get('pitch',0)))>.22):
            simulated_faults.add(v['id'])
        if v['id'] in simulated_faults:
            v['fault']=fault_status.get(v['id'],{'phase':'pending'})
            phase=v['fault']['phase']
            v['readiness'].update(available=False,reason='수행불가 시연 주입',operational_state='unavailable',task={'pending':'고장 명령 전달 대기','unstable':'비행 임무 중단 · 비상 복귀 준비','returning':'비상 복귀 중 · 새 임무 배정 불가','landing':'갑판 착함 중 · 새 임무 배정 불가','charging':'갑판 충전 · 정비 대기','moored':'함선 측면 동행 · 정비 대기'}.get(phase,phase))
            kind=fault_kinds.get(v['id'],'payload');v['fault_type']=kind
            v['fault_behavior']=FAULT_TYPES[kind]['uav_behavior' if v['type']=='UAV' else 'usv_behavior']
            v['readiness']['reason']=FAULT_TYPES[kind]['label']
            if kind=='propulsion':v['readiness']['task']='추진 정지 · 수면까지 비상 하강' if v['type']=='UAV' else '추진 차단 · 관성/부력에 따른 표류'
            if kind=='communication':
                v['simulation_pose']=v['telemetry'];v['telemetry']=fault_last_known.get(v['id']);v['connected']=False
                v['source']='last_known';v['communication_status']='실제 상태 확인 불가 · 마지막 관측'
                v['readiness']['task']='통신 두절 · 설정된 비상 모드 시연'
        if not v.get('fault') and max(abs((v['telemetry'] or {}).get('roll',0)),abs((v['telemetry'] or {}).get('pitch',0)))>.22:
            v['readiness'].update(available=False,reason='자세 불안정 · 배정 보류',operational_state='unavailable')
        if mission and mission.get('approved'):
            task=next((t for t in mission['approved']['tasks'] if t['vehicle']==v['id']),None)
            if task and not v.get("fault"):
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
    lead=latest.get('SHIP-01');stamp=lead.get('sim_time') if lead and now-lead['received_at']<5 else None
    if mission and mission.get('source')=='synthetic' and lead and stamp is not None:
        origin=mission.get('scene_origin')
        if not origin or stamp<origin['sim_time']:mission['scene_origin']={k:lead.get(k,0) for k in ('x','y','yaw','sim_time')}
        mission['scene_last_time']=stamp
    situations=scene_targets([mission],stamp) if mission and mission.get('source')=='synthetic' else []
    if situations:mission['target_world_current']=[situations[0]['x'],situations[0]['y']]
    return {'mission':mission,'scenario_catalog':SCENARIOS,'vehicles': vehicles, 'camera_available': camera is not None and now-camera['received_at'] < 5, 'model': MODEL, 'camera_source': 'selected vehicle inspection camera' if camera_view=='inspect' else 'SHIP-01 stabilized overhead sensors', 'scene_mode': FLEET['motion']['uav_pattern'], 'camera_view':camera_view,'inspection_vehicle':inspection_vehicle, 'formations': {**formation, 'catalog':CATALOG,'status':formation_status}, 'scene': {'camera':CAMERA_VIEWS[camera_view], 'motion':FLEET['motion'], 'scenario': None,'sim_time':stamp,'situations':situations}}

class FormationRequest(BaseModel):
    group: Literal['usv','uav']
    mode: str
@app.get('/api/formations')
async def get_formations():
    return {**formation,'catalog':CATALOG,'status':formation_status,'mission':mission,'inspection_vehicle':inspection_vehicle,'faults':list(simulated_faults),'fault_modes':{id:fault_kinds.get(id,'payload') for id in simulated_faults},'fault_states':fault_status,'availability':{v['id']:v['connected'] and v['id'] not in simulated_faults and (v['type']=='SHIP' or v['readiness']['battery_percent']>=35) for v in state()['vehicles']}}
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
    human_confirmed: bool = False
    decision_source: Literal['captain_button','captain_text'] = 'captain_button'
    operator_command: str = Field(default='',max_length=100)

@app.post('/api/mission/scenario')
async def start_scenario(data: ScenarioRequest):
    global mission,mission_counter,camera_view,camera
    if data.scenario=='fault':
        if not data.vehicle_id:raise HTTPException(422,'고장 대상 기체를 선택하세요.')
        await set_simulated_fault(data.vehicle_id,FaultRequest(unavailable=True,fault_type=data.fault_type))
        if camera_view!='wide':camera_view='wide';camera=None
        return {'ok':True,'vehicle_id':data.vehicle_id,'fault_type':data.fault_type,'source':'synthetic'}
    if mission and mission.get('approved'):raise HTTPException(409,'진행 중인 대응안을 먼저 종료하세요.')
    if camera_view!='wide':camera_view='wide';camera=None
    snapshot=state();plans=options(snapshot['vehicles'],formation,data.scenario)
    mission_counter+=1
    mission={'id':mission_counter,'scenario':data.scenario,'card':SCENARIOS[data.scenario],
             'created_at':time.time(),'basis_revision':formation['revision'],'options':plans,'approved':None,'source':'synthetic',
             'execution_scope':'승인 시 대형과 UAV 관측·복귀를 실행합니다. USV 확인 출동은 계획 등록입니다.'}
    lead=latest.get('SHIP-01')
    mission['scene_origin']={k:lead.get(k,0) for k in ('x','y','yaw','sim_time')} if lead and time.time()-lead['received_at']<5 else None
    return mission

@app.post('/api/mission/approve')
async def approve_plan(data: ApprovalRequest):
    if not data.human_confirmed:raise HTTPException(409,'운용자의 명시적 최종 승인이 필요합니다.')
    if not mission or mission['id']!=data.mission_id:raise HTTPException(409,'상황 카드가 변경되었습니다.')
    if mission.get('approved'):raise HTTPException(409,'이미 승인된 대응안입니다.')
    if mission.get('risk_id') and not any(r['id']==mission['risk_id'] for r in assess(state()['vehicles'])):raise HTTPException(409,'위험이 해소되었습니다. 최신 상황을 다시 검토하세요.')
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
    target=next(iter(state()['scene']['situations']),None)
    if target:mission['target_world']=[target['x'],target['y']]
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
    fault_type: Literal['payload','propulsion','communication'] = 'payload'
@app.post('/api/vehicles/{vehicle_id}/simulated-fault')
async def set_simulated_fault(vehicle_id: str,data: FaultRequest):
    if vehicle_id not in IDS or vehicle_id.startswith('SHIP'):raise HTTPException(422,'지원 기체를 선택하세요.')
    if data.unavailable:
        simulated_faults.add(vehicle_id);fault_kinds[vehicle_id]=data.fault_type
        fault_last_known[vehicle_id]=dict(latest[vehicle_id]) if vehicle_id in latest else None
        fault_status.pop(vehicle_id,None);risk_cache['evaluated_at']=0
    else:
        if vehicle_id.startswith('UAV'):
            kind=fault_kinds.get(vehicle_id,'payload');phase=fault_status.get(vehicle_id,{}).get('phase')
            measured=latest.get(vehicle_id)
            recovered=kind=='communication' or (kind=='payload' and phase=='charging') or (kind=='propulsion' and phase=='ditched' and measured and time.time()-measured['received_at']<5 and measured['z']<=1.5)
            if not recovered:raise HTTPException(409,'장비 고장은 착함·충전 후, 추진 고장은 수면 도달·회수 후 해제하세요.')
        simulated_faults.discard(vehicle_id);fault_status.pop(vehicle_id,None)
        fault_kinds.pop(vehicle_id,None);fault_last_known.pop(vehicle_id,None);risk_cache['evaluated_at']=0
    return {'ok':True,'source':'simulated'}

class FaultReport(BaseModel):
    tasks: dict
@app.post('/api/internal/faults')
async def report_faults(data: FaultReport,x_bridge_token: str=Header(default='')):
    if not TOKEN or not hmac.compare_digest(TOKEN,x_bridge_token):raise HTTPException(403,'Bridge token required')
    for id,value in data.tasks.items():
        if id not in simulated_faults:continue
        old=fault_status.get(id,{})
        if value.get('phase')=='charging':
            measured=latest.get(id);lead=latest.get('SHIP-01');slot=deck_slot(int(id[-2:]))
            on_deck=measured and lead and time.time()-measured['received_at']<5 and math.dist([measured[k] for k in ('x','y','z')],[lead['x']+slot[0],lead['y']+slot[1],slot[2]])<1.5
            if not on_deck:value={**value,'phase':'landing'}
        if value.get('phase')=='charging' and old.get('phase')=='charging':
            dt=max(0,min(2,value.get('sim_time',0)-old.get('sim_time',0)))
            charge_credit[id]=charge_credit.get(id,0)+dt*.2
        fault_status[id]=value
    return {'ok':True}

@app.get('/api/risks')
async def risks():
    if time.time()-risk_cache['evaluated_at']>=10:
        snapshot=state();items=assess(snapshot['vehicles'])
        lead=next((v for v in snapshot['vehicles'] if v['id']=='SHIP-01' and v['connected']),None)
        if items and lead:
            p=items[0]['telemetry'] or lead['telemetry']
            offset=[p['x']-lead['telemetry']['x'],p['y']-lead['telemetry']['y']]
            items[0]['options']=options(snapshot['vehicles'],formation,'rescue',target_offset=offset)
        risk_cache.update(evaluated_at=time.time(),items=items)
    return {**risk_cache,'interval_seconds':10,'source':'telemetry_demo_thresholds'}

@app.post('/api/risks/{risk_id}/plan')
async def risk_plan(risk_id: str):
    global mission,mission_counter
    if mission and mission.get('approved') and mission.get('execution',{}).get('status') not in ('completed','cancelled'):raise HTTPException(409,'승인 임무를 종료한 뒤 새 대응안을 검토하세요.')
    snapshot=state();risk=next((r for r in assess(snapshot['vehicles']) if r['id']==risk_id),None)
    if not risk:raise HTTPException(409,'위험 상태가 해소되었습니다. 다시 평가하세요.')
    lead=next((v for v in snapshot['vehicles'] if v['id']=='SHIP-01' and v['connected']),None)
    if not lead:raise HTTPException(409,'함선 위치 확인이 필요합니다.')
    p=risk['telemetry'] or lead['telemetry'];offset=[p['x']-lead['telemetry']['x'],p['y']-lead['telemetry']['y']]
    plans=options(snapshot['vehicles'],formation,'rescue',target_offset=offset)
    for plan,title in zip(plans,['현재 대형 유지 · 주변 관측','양측 종대 · 복귀 구역 확인','후방 V자 · 대체 기체 관측']):
        plan['title']=title
        for task in plan['tasks']:task['task']='고장·위험 구역 주변 관측' if task['vehicle'].startswith('UAV') else '착함 구역 연락 지원 계획'
    mission_counter+=1
    mission={'id':mission_counter,'scenario':'rescue','card':{'title':risk['title'],'summary':risk['evidence'],'offset':offset,'unknown':'규칙 기반 시연 임계값입니다. 실제 고장 진단·접촉 충전 하드웨어는 연결되지 않았습니다.'},'risk_id':risk_id,'created_at':time.time(),'basis_revision':formation['revision'],'options':plans,'approved':None,'source':'telemetry_rules'}
    return mission

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
    return {'mode':camera_view,'vehicle_id':inspection_vehicle, 'camera':CAMERA_VIEWS[camera_view]}

@app.post('/api/camera/view')
async def set_camera_view(data: CameraView):
    global camera_view,inspection_vehicle,camera
    if data.mode not in CAMERA_VIEWS:
        raise HTTPException(422, 'Camera view unavailable')
    if data.mode=='inspect':
        if data.vehicle_id not in IDS:raise HTTPException(422,'근접 관측할 기체를 선택하세요.')
        value=latest.get(data.vehicle_id)
        if not value or time.time()-value['received_at']>=5:raise HTTPException(409,'기체의 최신 위치가 필요합니다.')
        inspection_vehicle=data.vehicle_id
    camera_view = data.mode
    camera=None
    return {'mode':camera_view,'vehicle_id':inspection_vehicle, 'camera':CAMERA_VIEWS[camera_view]}

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
        fault_kinds.update(saved.get('fault_kinds',{}));fault_last_known.update(saved.get('fault_last_known',{}))
        fault_status.update(saved.get('fault_status',{}));charge_credit.update(saved.get('charge_credit',{}))
    except (OSError,ValueError,KeyError,TypeError):pass

def save_console():
    CONSOLE_SNAPSHOT.parent.mkdir(exist_ok=True)
    data={'formation':formation,'mission':mission,'mission_counter':mission_counter,'faults':list(simulated_faults),'battery_origin':battery_origin,'fault_status':fault_status,'charge_credit':charge_credit,'fault_kinds':fault_kinds,'fault_last_known':fault_last_known}
    temp=CONSOLE_SNAPSHOT.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(CONSOLE_SNAPSHOT)

app.mount('/', StaticFiles(directory=ROOT/'frontend', html=True), name='frontend')
