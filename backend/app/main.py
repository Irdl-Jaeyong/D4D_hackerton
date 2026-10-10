import asyncio
from contextlib import asynccontextmanager, suppress
import base64
import hmac
import math
import logging
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
from auto_scenarios import ScenarioGenerator
from risk_monitor import assess
from fault_motion import deck_slot
from scenario_scene import targets as scene_targets
from .approval_risk import evaluate,sort_key,CONFIG as RISK_CONFIG
mission=None # only the human-approved execution; pending cards live in missions
missions={}
mission_counter=0
formation={'usv':'circle','uav':'hemisphere','revision':0}
formation_status={}
auto_generator=None
@asynccontextmanager
async def console_lifespan(application):
    global auto_generator
    restore_console()
    auto_generator=ScenarioGenerator(json.loads((ROOT/'config/auto_scenarios.json').read_text()),now=time.monotonic())
    auto_task=asyncio.create_task(generate_random_scenarios())
    try:
        yield
    finally:
        auto_task.cancel()
        with suppress(asyncio.CancelledError):await auto_task
        save_console()

async def generate_random_scenarios():
    while True:
        await asyncio.sleep(1)
        request=auto_generator.next_request(state(),time.monotonic())
        if request:
            try:
                item=await start_scenario(ScenarioRequest(**request),preserve_camera=True)
                item['auto_generated']=True
                save_console()
            except HTTPException as error:
                logging.getLogger(__name__).warning('Automatic scenario skipped: %s',error.detail)

app = FastAPI(title='NAVIS-AI preparation MVP', lifespan=console_lifespan)
latest = {}
battery_origin = {}
simulated_faults=set()
automatic_returns=set()
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
            ready=v['connected'] and v['readiness']['battery_percent']>=35
            v['readiness'].update(available=ready,reason='배정 가능' if ready else v['readiness']['reason'],operational_state=('waiting' if v['type']=='UAV' else 'defending') if ready else 'unavailable')
        if v['type']=='UAV' and v['connected'] and (v['readiness']['battery_percent']<35 or max(abs((v['telemetry'] or {}).get('roll',0)),abs((v['telemetry'] or {}).get('pitch',0)))>.22):
            simulated_faults.add(v['id'])
            if v['id'] not in fault_kinds:automatic_returns.add(v['id'])
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
                v['readiness']['task']=task['task']+' · 출동 준비'
                v['readiness']['available']=False
                execution=mission.get('execution',{}).get('tasks',{}).get(v['id'])
                if execution:
                    labels={'outbound':'출동 중','observing':'현장 확인 중','returning':'복귀 중','completed':'완료 · 대형 유지'}
                    v['readiness']['task']=task['task']+' · '+labels.get(execution['stage'],'확인 필요')
                    if execution.get('blocked'):v['readiness'].update(operational_state='unavailable',reason='임무 중 상태 확인 필요')
                    elif v['readiness']['operational_state']!='unavailable':
                        v['readiness']['operational_state']='waiting' if execution['stage']=='completed' else 'defending'
                        v['readiness']['reason']='실측 위치 기반 임무 진행'
                if not execution and v['readiness']['operational_state']!='unavailable':
                    v['readiness']['operational_state']='waiting'
                    v['readiness']['reason']='Gazebo 출동 명령 전달 대기'
    lead=latest.get('SHIP-01');stamp=lead.get('sim_time') if lead and now-lead['received_at']<5 else None
    for item in missions.values():
        if item.get('source')=='synthetic' and item['scenario']!='fault' and lead and stamp is not None:
            origin=item.get('scene_origin')
            if not origin or stamp<origin['sim_time']:item['scene_origin']={k:lead.get(k,0) for k in ('x','y','yaw','sim_time')}
            item['scene_last_time']=stamp
    situations=scene_targets([m for m in missions.values() if m.get('source')=='synthetic'],stamp)
    for target in situations:missions[target['mission_id']]['target_world_current']=[target['x'],target['y']]
    reassess_missions(vehicles)
    queue=sorted((m for m in missions.values() if not m.get('approved')),key=sort_key)
    return {'auto_scenarios':{'enabled':auto_generator.config['enabled'],'next_in_seconds':max(0,round(auto_generator.next_at-time.monotonic())),'max_pending':auto_generator.config['max_pending']} if auto_generator else None,'mission':mission or next(iter(queue),None),'active_mission':mission,'approval_queue':queue,'scenario_catalog':SCENARIOS,'vehicles': vehicles, 'camera_available': camera is not None and now-camera['received_at'] < 5, 'model': MODEL, 'camera_source': 'selected vehicle inspection camera' if camera_view=='inspect' else 'SHIP-01 stabilized overhead sensors', 'scene_mode': FLEET['motion']['uav_pattern'], 'camera_view':camera_view,'inspection_vehicle':inspection_vehicle, 'formations': {**formation, 'catalog':CATALOG,'status':formation_status}, 'scene': {'camera':CAMERA_VIEWS[camera_view], 'motion':FLEET['motion'], 'scenario': None,'sim_time':stamp,'situations':situations}}

def fault_signals(vehicle_id):
    kind=fault_kinds.get(vehicle_id,'payload');criteria=FAULT_TYPES[kind]
    p=latest.get(vehicle_id);fresh=p and time.time()-p['received_at']<5
    return {**{k:criteria[k] for k in ('S','U','A')},'reason':criteria['label']+' · 고장 종류별 시연 기준',
            'severe_control_loss':bool(kind=='propulsion' and vehicle_id.startswith('UAV') and fresh and p.get('z',0)>1.5)}

def reassess_missions(vehicles):
    live_risks={r['id']:r for r in assess(vehicles)}
    for item in missions.values():
        if item.get('approved'):continue # approval evidence is immutable
        item['resolved']=False
        if item['scenario']=='fault':
            item['resolved']=item['vehicle_id'] not in simulated_faults
            signals={} if item['resolved'] else fault_signals(item['vehicle_id'])
        elif item.get('risk_id'):
            current=live_risks.get(item['risk_id']);item['resolved']=current is None
            if not current:signals={}
            elif current['kind']=='fault':signals=fault_signals(current['vehicle'])
            else:
                kind='separation' if current['kind'].startswith('separation') else current['kind']
                signals={**RISK_CONFIG['risk_kinds'].get(kind,{}),'reason':current['evidence']}
        else:signals=RISK_CONFIG['scenarios'].get(item['scenario'],{})
        item['risk']=evaluate(signals);item['risk']['source']=item['source']
        if item['resolved']:item['risk']['reason']='원인 해소 · 상황 종료 가능'

def pending_plans(item,vehicles):
    lead=latest.get('SHIP-01');target=item.get('target_world_current')
    if item['scenario']=='fault':
        target=fault_last_known.get(item['vehicle_id']) if fault_kinds.get(item['vehicle_id'])=='communication' else latest.get(item['vehicle_id'])
        target=[target['x'],target['y']] if target else None
    if target and lead:
        offset=[target[0]-lead['x'],target[1]-lead['y']]
    else:offset=item['card']['offset']
    if item['scenario']=='fault' or item.get('risk_id'):item['card']['offset']=offset
    if lead:item['plan_target_world']=[lead['x']+offset[0],lead['y']+offset[1]]
    return options(vehicles,formation,'rescue' if item['scenario']=='fault' else item['scenario'],target_offset=offset)

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
    decision_source: Literal['captain_button','captain_text','response_button'] = 'captain_button'
    operator_command: str = Field(default='',max_length=100)
    plan_revision: int = Field(default=0,ge=0)

@app.post('/api/mission/scenario')
async def start_scenario(data: ScenarioRequest,preserve_camera: bool=False):
    global mission_counter,camera_view,camera
    if data.scenario=='fault':
        if not data.vehicle_id:raise HTTPException(422,'고장 대상 기체를 선택하세요.')
        await set_simulated_fault(data.vehicle_id,FaultRequest(unavailable=True,fault_type=data.fault_type))
    if not preserve_camera and camera_view!='wide':camera_view='wide';camera=None
    mission_counter+=1
    lead=latest.get('SHIP-01');origin={k:lead.get(k,0) for k in ('x','y','yaw','sim_time')} if lead and time.time()-lead['received_at']<5 else None
    if data.scenario=='fault':
        measured=latest.get(data.vehicle_id)
        offset=[measured['x']-lead['x'],measured['y']-lead['y']] if measured and lead else [0,0]
        card={'title':data.vehicle_id+' · '+FAULT_TYPES[data.fault_type]['label'],'summary':FAULT_TYPES[data.fault_type]['uav_behavior' if data.vehicle_id.startswith('UAV') else 'usv_behavior'],'offset':offset,'unknown':'모의 고장 · 상황 종료와 기체 정비 해제는 별도입니다.'}
    else:card=SCENARIOS[data.scenario]
    now=time.time()
    item={'id':mission_counter,'scenario':data.scenario,'card':card,'created_at':now,'planned_at':now,'plan_revision':0,
          'basis_revision':formation['revision'],'options':[],'approved':None,'source':'synthetic','scene_origin':origin,
          'scene_slot':1+max((m.get('scene_slot',0) for m in missions.values() if m['scenario']==data.scenario),default=-1),
          'execution_scope':'선택 시 대형 변경과 UAV·USV 출동·확인·복귀를 실행합니다.'}
    if data.scenario=='fault':item.update(vehicle_id=data.vehicle_id,fault_type=data.fault_type)
    missions[item['id']]=item
    snapshot=state();item['options']=pending_plans(item,snapshot['vehicles'])
    return item

@app.post('/api/mission/{mission_id}/refresh')
async def refresh_plan(mission_id: int):
    item=missions.get(mission_id)
    if not item:raise HTTPException(404,'상황을 찾을 수 없습니다.')
    if item.get('approved'):raise HTTPException(409,'승인된 계획은 다시 계산할 수 없습니다.')
    snapshot=state()
    if item.get('resolved'):raise HTTPException(409,'원인이 해소되었습니다. 상황을 종료하세요.')
    if item.get('risk_id'):
        current=next((r for r in assess(snapshot['vehicles']) if r['id']==item['risk_id']),None)
        lead=latest.get('SHIP-01');p=current and current['telemetry']
        if p and lead:item['card']['offset']=[p['x']-lead['x'],p['y']-lead['y']]
    item['options']=pending_plans(item,snapshot['vehicles']);item['basis_revision']=formation['revision']
    item['planned_at']=time.time();item['plan_revision']=item.get('plan_revision',0)+1
    return item

@app.post('/api/mission/approve')
async def approve_plan(data: ApprovalRequest):
    global mission
    item=missions.get(data.mission_id)
    if mission:raise HTTPException(409,'승인 임무를 종료한 뒤 다음 상황을 승인하세요.')
    if not data.human_confirmed:raise HTTPException(409,'운용자의 명시적 최종 승인이 필요합니다.')
    if not item or item['id']!=data.mission_id:raise HTTPException(409,'상황 카드가 변경되었습니다.')
    if item.get('approved'):raise HTTPException(409,'이미 승인된 대응안입니다.')
    state()
    if item.get('resolved'):raise HTTPException(409,'원인이 해소되었습니다. 상황을 종료하세요.')
    if data.plan_revision!=item.get('plan_revision',0):raise HTTPException(409,'추천이 갱신되었습니다. 다시 검토하세요.')
    if item.get('risk_id') and not any(r['id']==item['risk_id'] for r in assess(state()['vehicles'])):raise HTTPException(409,'위험이 해소되었습니다. 최신 상황을 다시 검토하세요.')
    if time.time()-item.get('planned_at',item['created_at'])>60:raise HTTPException(409,'추천이 60초 이상 지났습니다. 최신 상태로 다시 계산하세요.')
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
    target=next((t for t in state()['scene']['situations'] if t['mission_id']==item['id']),None)
    if target:item['target_world']=[target['x'],target['y']]
    elif item.get('plan_target_world'):item['target_world']=item['plan_target_world']
    item['approved']={**plan,'approved_at':time.time(),'formation_revision':formation['revision'],'decision_source':data.decision_source,'operator_command':data.operator_command,'human_confirmed':True}
    item['energy_at_start']={t['vehicle']:current[t['vehicle']]['readiness']['battery_percent'] for t in plan['tasks']}
    item['execution']={'status':'pending','tasks':{}}
    item['risk_at_approval']=json.loads(json.dumps(item['risk']));mission=item
    return item

class CancelRequest(BaseModel):
    mission_id: int | None = None
@app.post('/api/mission/cancel')
async def cancel_plan(data: CancelRequest | None = None):
    global mission
    id=data.mission_id if data and data.mission_id is not None else (mission or next(iter(sorted((m for m in missions.values() if not m.get('approved')),key=sort_key)),{})).get('id')
    item=missions.get(id)
    if not item:raise HTTPException(404,'상황을 찾을 수 없습니다.')
    if item.get('approved') and item.get('execution',{}).get('status') not in ('completed','cancelled'):
        item['cancel_requested']=True
        return {'ok':True,'message':'취소 요청 · 출동한 UAV·USV가 대형으로 복귀합니다.'}
    missions.pop(id)
    if mission and mission['id']==id:mission=None
    return {'ok':True,'message':'선택한 상황 종료 · 나머지 상황과 현재 대형 유지'}

class ExecutionReport(BaseModel):
    mission_id: int
    sim_time: float = Field(ge=0,allow_inf_nan=False)
    elapsed_seconds: float = Field(ge=0,allow_inf_nan=False)
    tasks: dict
    status: Literal['running','completed','cancelled']
    cancelled: bool = False
@app.post('/api/internal/execution')
async def report_execution(data: ExecutionReport,x_bridge_token: str=Header(default='')):
    global mission
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
            remaining=readiness({'id':id,'type':id.split('-')[0],'connected':True,'telemetry':current},max(0,current['sim_time']-battery_origin.get(id,0)))['battery_percent']
            task['simulated_battery_used']=round(max(0,mission['energy_at_start'].get(id,remaining)-remaining),1)
    if data.status in ('completed','cancelled'):mission=None
    return {'ok':True}

class FaultRequest(BaseModel):
    unavailable: bool
    fault_type: Literal['payload','propulsion','communication'] = 'payload'
@app.post('/api/vehicles/{vehicle_id}/simulated-fault')
async def set_simulated_fault(vehicle_id: str,data: FaultRequest):
    if vehicle_id not in IDS or vehicle_id.startswith('SHIP'):raise HTTPException(422,'지원 기체를 선택하세요.')
    if data.unavailable:
        simulated_faults.add(vehicle_id);automatic_returns.discard(vehicle_id);fault_kinds[vehicle_id]=data.fault_type
        fault_last_known[vehicle_id]=dict(latest[vehicle_id]) if vehicle_id in latest else None
        fault_status.pop(vehicle_id,None);risk_cache['evaluated_at']=0
    else:
        if vehicle_id.startswith('UAV'):
            kind=fault_kinds.get(vehicle_id,'payload');phase=fault_status.get(vehicle_id,{}).get('phase')
            measured=latest.get(vehicle_id)
            recovered=kind=='communication' or (kind=='payload' and phase=='charging') or (kind=='propulsion' and phase=='ditched' and measured and time.time()-measured['received_at']<5 and measured['z']<=1.5)
            if not recovered:raise HTTPException(409,'장비 고장은 착함·충전 후, 추진 고장은 수면 도달·회수 후 해제하세요.')
        simulated_faults.discard(vehicle_id);automatic_returns.discard(vehicle_id);fault_status.pop(vehicle_id,None)
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
        if id in automatic_returns and value.get('phase')=='charging' and measured:
            base=readiness({'id':id,'type':'UAV','connected':True},max(0,measured['sim_time']-battery_origin.get(id,0)))['battery_percent']
            if base+charge_credit.get(id,0)>=80:
                battery_origin[id]=measured['sim_time']
                initial=readiness({'id':id,'type':'UAV','connected':True},0)['battery_percent']
                charge_credit[id]=80-initial
                simulated_faults.discard(id);automatic_returns.discard(id);fault_status.pop(id,None)
                risk_cache['evaluated_at']=0
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
    global mission_counter
    existing=next((m for m in missions.values() if m.get('risk_id')==risk_id and not m.get('approved')),None)
    if existing:return await refresh_plan(existing['id'])
    snapshot=state();risk=next((r for r in assess(snapshot['vehicles']) if r['id']==risk_id),None)
    if not risk:raise HTTPException(409,'위험 상태가 해소되었습니다. 다시 평가하세요.')
    lead=next((v for v in snapshot['vehicles'] if v['id']=='SHIP-01' and v['connected']),None)
    if not lead:raise HTTPException(409,'함선 위치 확인이 필요합니다.')
    p=risk['telemetry'] or lead['telemetry'];offset=[p['x']-lead['telemetry']['x'],p['y']-lead['telemetry']['y']]
    plans=options(snapshot['vehicles'],formation,'rescue',target_offset=offset)
    for plan,title in zip(plans,['현재 대형 유지 · 주변 관측','양측 종대 · 복귀 구역 확인','후방 V자 · 대체 기체 관측']):
        plan['title']=title
        for task in plan['tasks']:task['task']='고장·위험 구역 주변 관측' if task['vehicle'].startswith('UAV') else '착함 구역 연락 지원'
    mission_counter+=1
    item={'id':mission_counter,'scenario':'rescue','card':{'title':risk['title'],'summary':risk['evidence'],'offset':offset,'unknown':'규칙 기반 시연 임계값입니다. 실제 고장 진단·접촉 충전 하드웨어는 연결되지 않았습니다.'},'risk_id':risk_id,'created_at':time.time(),'basis_revision':formation['revision'],'options':plans,'approved':None,'source':'telemetry_rules','planned_at':time.time(),'plan_revision':0}
    missions[item['id']]=item;state()
    return item

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
                  '카메라는 함대 전체를 비스듬히 내려다보는 Gazebo 항공 관측 카메라입니다. 메인 함선은 직선 전진하고 USV와 드론은 선택된 함선 상대 대형을 유지합니다. USV는 추진력 기반, 드론은 위치 갱신 기반 시연입니다. 배터리는 시뮬레이션 추정값입니다. 상황과 대응안은 규칙 기반 시연이며 승인된 UAV 관측·복귀는 Gazebo에서 실행됩니다. 배정된 USV도 추진력으로 현장 확인 후 복귀합니다. 위험도와 우선순위는 제공된 규칙 계산 결과만 설명하고 재평가하거나 수정하지 마세요. S/U/A는 시연 기준이며 측정값과 구분하세요. 보이는 것만 설명하고 불확실하면 명시하세요. '
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
        formation.update(saved['formation']);mission=None
        cards=saved.get('missions') or ([saved['mission']] if saved.get('mission') else [])
        missions.clear();missions.update({m['id']:m for m in cards})
        mission=next((m for m in cards if m.get('approved') and m.get('execution',{}).get('status') not in ('completed','cancelled')),None)
        mission_counter=max(saved.get('mission_counter',0),max(missions,default=0))
        simulated_faults.update(id for id in saved.get('faults',[]) if id in IDS)
        battery_origin.update(saved.get('battery_origin',{}))
        fault_kinds.update(saved.get('fault_kinds',{}));automatic_returns.update(saved.get('automatic_returns',set(saved.get('faults',[]))-set(saved.get('fault_kinds',{}))));fault_last_known.update(saved.get('fault_last_known',{}))
        fault_status.update(saved.get('fault_status',{}));charge_credit.update(saved.get('charge_credit',{}))
    except (OSError,ValueError,KeyError,TypeError):pass

def save_console():
    CONSOLE_SNAPSHOT.parent.mkdir(exist_ok=True)
    data={'formation':formation,'mission':mission,'missions':list(missions.values()),'mission_counter':mission_counter,'faults':list(simulated_faults),'automatic_returns':list(automatic_returns),'battery_origin':battery_origin,'fault_status':fault_status,'charge_credit':charge_credit,'fault_kinds':fault_kinds,'fault_last_known':fault_last_known}
    temp=CONSOLE_SNAPSHOT.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(CONSOLE_SNAPSHOT)

app.mount('/', StaticFiles(directory=ROOT/'frontend', html=True), name='frontend')
