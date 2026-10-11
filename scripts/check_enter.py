#!/usr/bin/env python3
"""Read-only readiness checks for the one-command local stack."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.request


def get(base, path):
    with urllib.request.urlopen(base.rstrip('/') + path, timeout=4) as response:
        return response.read()


def receiving_ids(state, now=None):
    now = time.time() if now is None else now
    result = set()
    for vehicle in state['vehicles']:
        if vehicle['connected']:
            result.add(vehicle['id'])
        elif vehicle.get('fault_type') == 'communication':
            # A demo communication fault deliberately hides operational
            # telemetry. Its separate simulation_pose still proves the bridge
            # is receiving; it must never count as an operational connection.
            pose = vehicle.get('simulation_pose') or {}
            age = now - pose.get('received_at', 0)
            if 0 <= age < 3:
                result.add(vehicle['id'])
    return result


def check(mode):
    base = os.environ.get('NAVIS_BACKEND_URL', 'http://127.0.0.1:18083')
    model = os.environ.get('OLLAMA_MODEL', 'minicpm-v4.5:latest')
    if mode == 'ollama':
        data = json.loads(get(os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'), '/api/tags'))
        if model not in [item['name'] for item in data['models']]:
            raise ValueError(f'모델 없음: {model}. scripts/ollama.sh pull {model} 실행 필요')
        return {'ollama': 'ok', 'model': model}
    health = json.loads(get(base, '/api/health'))
    if health.get('ollama') != 'ok' or not health.get('model_installed') or health.get('model') != model:
        raise ValueError('웹의 Ollama 연결 또는 모델 설정을 확인하세요.')
    if mode == 'web':
        return health
    state = json.loads(get(base, '/api/state'))
    fleet = json.loads((Path(__file__).resolve().parents[1] / 'config/fleet.json').read_text())
    expected = {f'{kind}-{i:02}' for kind, key in [('SHIP', 'ships'), ('UAV', 'uavs'), ('USV', 'usvs')] for i in range(1, fleet[key] + 1)}
    connected = {v['id'] for v in state['vehicles'] if v['connected']}
    receiving = receiving_ids(state)
    result = {**health, 'connected': len(connected), 'receiving': len(receiving), 'total': len(expected), 'camera_available': state['camera_available'], 'web': base}
    if mode == 'live':
        if receiving != expected or not state['camera_available']:
            raise ValueError(f'데이터 수신 {len(receiving)}/{len(expected)} · 운용 연결 {len(connected)} · 영상 {state["camera_available"]}')
        if not get(base, '/api/camera').startswith(b'\xff\xd8'):
            raise ValueError('카메라 JPEG 미수신')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['ollama', 'web', 'live', 'status'])
    parser.add_argument('--timeout', type=float, default=0)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout
    last = None
    while True:
        try:
            print(json.dumps(check(args.mode), ensure_ascii=False), flush=True)
            break
        except (OSError, ValueError, KeyError) as error:
            if str(error) != last:
                print(str(error), flush=True)
                last = str(error)
            if time.monotonic() >= deadline:
                raise SystemExit(f'준비 실패 ({args.mode}). D4D_enter logs로 확인하세요.')
            time.sleep(1)
