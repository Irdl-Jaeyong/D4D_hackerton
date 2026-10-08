#!/usr/bin/env python3
"""Read live Gazebo camera/stats and test Ollama while simulation runs."""
import base64, json, os, subprocess, threading, time, urllib.request
from pathlib import Path
from PIL import Image
os.environ.setdefault('GZ_PARTITION', 'd4d-vlm-check')
from gz.transport13 import Node
from gz.msgs10.image_pb2 import Image as ImageMsg
from gz.msgs10.world_stats_pb2 import WorldStatistics
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/gazebo_vlm'
OUT.mkdir(parents=True, exist_ok=True)
node = Node()
frame = [None]
stats = [None]
count = [0]
ready = threading.Event()
def camera(msg):
    frame[0] = msg
    count[0] += 1
    ready.set()
def statistics(msg):
    stats[0] = {'iterations': msg.iterations, 'sim_seconds': msg.sim_time.sec + msg.sim_time.nsec/1e9, 'real_time_factor': msg.real_time_factor, 'paused': msg.paused}
node.subscribe(ImageMsg, '/camera', camera)
node.subscribe(WorldStatistics, '/world/camera_sensor/stats', statistics)
if not ready.wait(25):
    raise RuntimeError('No Gazebo camera data')
results = []
for i in range(3):
    msg = frame[0]
    imagepath = OUT / f'camera_nvidia_{i+1}.png'
    Image.frombytes('RGB', (msg.width, msg.height), msg.data, 'raw', 'RGB', msg.step).save(imagepath)
    payload = {'model':'minicpm-v4.5:latest', 'stream':True, 'think':False, 'keep_alive':'5m', 'options':{'temperature':0,'num_ctx':4096,'num_predict':256}, 'messages':[{'role':'user','content':'이 시뮬레이션 카메라 이미지에서 보이는 물체의 색상, 모양, 위치를 한국어로 간단히 설명하세요. 잘린 물체는 잘렸다고 말하세요.','images':[base64.b64encode(imagepath.read_bytes()).decode()]}]}
    before_stats = stats[0]
    before_count = count[0]
    samples = []
    stop = threading.Event()
    def gpu():
        while not stop.is_set():
            raw = subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
            samples.append(raw.strip())
            stop.wait(0.25)
    t = threading.Thread(target=gpu,daemon=True); t.start()
    start = time.perf_counter(); first = None; answer = ''; final = {}
    print('START',i+1,flush=True)
    try:
        req = urllib.request.Request('http://127.0.0.1:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=180) as response:
            for line in response:
                chunk = json.loads(line)
                if 'error' in chunk: raise RuntimeError(chunk['error'])
                part = chunk.get('message',{}).get('content','')
                if part and first is None: first = time.perf_counter()-start
                answer += part
                if chunk.get('done'): final = chunk
    finally:
        stop.set(); t.join(timeout=4)
    result = {'trial':i+1,'image':str(imagepath.relative_to(ROOT)), 'answer':answer, 'first_content_seconds':first,'elapsed_seconds':time.perf_counter()-start,'stats_before':before_stats,'stats_after':stats[0], 'camera_frames_received':count[0]-before_count,'gpu_samples':samples,'metrics':{k:v for k,v in final.items() if k not in ('message','model','created_at')}}
    results.append(result)
    (OUT/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='gpu_samples'},ensure_ascii=False),flush=True)
