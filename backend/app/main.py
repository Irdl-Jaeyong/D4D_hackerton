import asyncio
import base64
import hmac
import json
import os
import time
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title='NAVIS-AI preparation MVP')
latest = {}
camera = None
lock = asyncio.Lock()
chat_lock = asyncio.Lock()
TOKEN = os.environ.get('NAVIS_BRIDGE_TOKEN', '')
MODEL = os.environ.get('OLLAMA_MODEL', 'minicpm-v4.5:latest')
OLLAMA = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
FLEET = json.loads((ROOT/'config/fleet.json').read_text())
IDS = [f'{kind}-{i:02}' for kind, key in [('SHIP','ships'),('UAV','uavs'),('USV','usvs')] for i in range(1, FLEET[key]+1)]
CAMERA_VEHICLE = FLEET['camera_vehicle']

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
    return {'vehicles': vehicles, 'camera_available': camera is not None and now-camera['received_at'] < 5, 'model': MODEL, 'camera_source': 'fleet_observer', 'scene_mode': 'hemisphere_figure_eight', 'scene': {'camera':FLEET['camera'], 'motion':FLEET['motion']}}

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
                  '카메라는 함대 전체를 비스듬히 내려다보는 Gazebo 항공 관측 카메라입니다. 메인 함선은 직선 전진하며 호위 USV 10대는 함선 상대 경계를 연속 교대하고, 드론 40대는 함선 위 반구 대형을 유지하면서 작은 8자 순찰과 위치 교대를 수행합니다. 이는 Gazebo 위치 갱신 시연이며 실제 항해 및 비행 제어는 아닙니다. 보이는 것만 설명하고 불확실하면 명시하세요. '
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
