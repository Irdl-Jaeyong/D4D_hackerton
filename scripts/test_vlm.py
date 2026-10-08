#!/usr/bin/env python3
"""MiniCPM-V smoke checks; writes raw responses and timings outside tracked source."""
import base64
import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'vlm_test'
OUT.mkdir(parents=True, exist_ok=True)
MODEL = 'minicpm-v4.5:latest'
BASE = 'http://127.0.0.1:11434'
img = Image.new('RGB', (640, 480), 'white')
draw = ImageDraw.Draw(img)
draw.rectangle((70, 140, 210, 280), fill='red')
draw.ellipse((390, 140, 530, 280), fill='blue')
img.save(OUT / 'shapes.png')
encoded = base64.b64encode((OUT / 'shapes.png').read_bytes()).decode()
swapped = Image.new('RGB', (640, 480), 'white')
sd = ImageDraw.Draw(swapped)
sd.ellipse((70, 140, 210, 280), fill='blue')
sd.rectangle((390, 140, 530, 280), fill='red')
swapped.save(OUT / 'shapes_swapped.png')
swapped_encoded = base64.b64encode((OUT / 'shapes_swapped.png').read_bytes()).decode()
cases = [
    ('text_cold', '한국어로 한 문장만 답하세요. UAV-01 배터리 80%, UAV-02 배터리 20%입니다. 배터리가 더 낮은 기체와 수치를 알려주세요.', None),
    ('text_warm', '한국어로 한 문장만 답하세요. UAV-01 배터리 80%, UAV-02 배터리 20%입니다. 배터리가 더 낮은 기체와 수치를 알려주세요.', None),
    ('image', '이미지에 있는 도형의 개수, 각 도형의 색상과 모양, 왼쪽/오른쪽 위치를 한국어로 간단히 설명하세요.', encoded),
    ('command_json', '사용자 요청: UAV-02의 상태를 조회해줘. 실행하지 말고 요청을 해석하세요. action은 get_status, vehicle_id는 대상 기체 식별자로 JSON에 기록하세요.', None),
]
cases.extend([
    ('text_new_warm', 'USV-01 배터리는 67%, USV-02는 43%입니다. 더 높은 기체와 배터리 차이를 한국어 한 문장으로 답하세요.', None),
    ('image_new_warm', '도형은 몇 개인가요? 각 도형의 위치, 색상, 모양을 한국어로 답하세요.', swapped_encoded),
])
results = []
for name, prompt, picture in cases:
    message = {'role': 'user', 'content': prompt}
    if picture:
        message['images'] = [picture]
    payload = {'model': MODEL, 'messages': [message], 'stream': True,
               'think': False, 'keep_alive': '5m',
               'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 256}}
    if name == 'command_json':
        payload['format'] = {'type': 'object', 'properties': {'action': {'type': 'string'}, 'vehicle_id': {'type': 'string'}}, 'required': ['action', 'vehicle_id'], 'additionalProperties': False}
    stop = threading.Event()
    samples = []
    def sample_gpu():
        while not stop.is_set():
            try:
                raw = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True, timeout=3)
                samples.append(raw.strip())
            except Exception:
                pass
            stop.wait(0.25)
    sampler = threading.Thread(target=sample_gpu, daemon=True)
    sampler.start()
    start = time.perf_counter()
    first = None
    answer = ''
    final = {}
    result = {'name': name, 'prompt': prompt}
    print('START', name, flush=True)
    try:
        request = urllib.request.Request(BASE + '/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=180) as response:
            for line in response:
                chunk = json.loads(line)
                if 'error' in chunk:
                    raise RuntimeError(chunk['error'])
                part = chunk.get('message', {}).get('content', '')
                if part and first is None:
                    first = time.perf_counter() - start
                answer += part
                if chunk.get('done'):
                    final = chunk
        result.update(answer=answer, first_content_seconds=first, elapsed_seconds=time.perf_counter()-start, metrics={key:value for key,value in final.items() if key not in ('message','model','created_at')})
    except Exception as error:
        result.update(error=str(error), elapsed_seconds=time.perf_counter()-start)
    finally:
        stop.set()
        sampler.join(timeout=4)
    result['gpu_samples'] = samples
    results.append(result)
    (OUT/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key != 'gpu_samples'}, ensure_ascii=False), flush=True)
print('RESULTS', OUT/'results.json', flush=True)
