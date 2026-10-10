"""Foreground, localhost-only demo supervisor. Ctrl+C stops only its children."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "record-explainer-v2"
MODEL = "qwen3:4b-instruct-2507-q4_K_M"
BIN = ROOT / "local-tools/ollama/bin/ollama"
MODELS = ROOT / "local-tools/ollama/models"
MANIFEST = MODELS / "manifests/registry.ollama.ai/library/qwen3/4b-instruct-2507-q4_K_M"

def preflight(model_port=11434, web_port=18080):
    if not (1024 <= model_port <= 65535 and 1024 <= web_port <= 65535) or model_port == web_port:
        raise RuntimeError("서로 다른 1024~65535 포트 두 개가 필요합니다.")
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise RuntimeError("프로젝트 .venv/bin/python으로 실행하세요.")
    versions = {name: importlib.metadata.version(name) for name in ("fastapi", "uvicorn", "httpx", "pydantic")}
    if not BIN.is_file() or not os.access(BIN, os.X_OK):
        raise RuntimeError("프로젝트 Ollama 실행 파일이 없습니다.")
    if not (Path.home() / ".ollama/id_ed25519").is_file():
        raise RuntimeError("기존 Ollama 키 파일이 없습니다. 이 시작 도구는 인증정보를 생성하지 않습니다.")
    if not MANIFEST.is_file():
        raise RuntimeError(f"모델 {MODEL}이 없습니다. 자동 다운로드하지 않습니다.")
    manifest = json.loads(MANIFEST.read_text())
    for item in [manifest["config"], *manifest["layers"]]:
        blob = MODELS / "blobs" / item["digest"].replace(":", "-")
        if not blob.is_file() or blob.stat().st_size != item["size"]:
            raise RuntimeError("모델 파일 누락 또는 크기 불일치. 설치를 확인하세요.")
    for port in (model_port, web_port):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as error:
                raise RuntimeError(f"localhost {port} 포트를 사용할 수 없습니다. 기존 작업을 종료하지 않습니다.") from error
    return versions

def get_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=2) as response:
        return json.load(response)

def wait_ready(child, url, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("시작한 프로세스가 종료됐습니다. demo 로그를 확인하세요.")
        try:
            return get_json(url)
        except (OSError, ValueError):
            time.sleep(.2)
    raise RuntimeError("서버 준비 시간이 초과됐습니다.")

def stop(children):
    for child in reversed(children):
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                child.wait(timeout=3)
                continue
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=3)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "start"])
    parser.add_argument("--model-port", type=int, default=11434)
    parser.add_argument("--web-port", type=int, default=18080)
    args = parser.parse_args()
    children, logs = [], []
    def terminate(signum, frame):
        raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        print("사전 점검 통과:", json.dumps(preflight(args.model_port, args.web_port), ensure_ascii=False), flush=True)
        if args.action == "check":
            return 0
        env = os.environ.copy()
        env.update(OLLAMA_HOST=f"127.0.0.1:{args.model_port}", OLLAMA_MODELS=str(MODELS), OLLAMA_CONTEXT_LENGTH="4096", OLLAMA_NO_CLOUD="1", D4D_OLLAMA_URL=f"http://127.0.0.1:{args.model_port}/api/generate")
        for name in ("ollama", "api"):
            logs.append((APP / f"demo-{name}.log").open("a"))
        children.append(subprocess.Popen([str(BIN), "serve"], env=env, stdout=logs[0], stderr=subprocess.STDOUT, start_new_session=True))
        wait_ready(children[0], f"http://127.0.0.1:{args.model_port}/api/version")
        models = get_json(f"http://127.0.0.1:{args.model_port}/api/tags")["models"]
        if not any(m["name"] == MODEL for m in models):
            raise RuntimeError("실행된 Ollama에서 지정 모델을 확인할 수 없습니다.")
        children.append(subprocess.Popen([sys.executable,"-m","uvicorn","app:app","--app-dir",str(APP),"--host","127.0.0.1","--port",str(args.web_port)], env=env, stdout=logs[1], stderr=subprocess.STDOUT, start_new_session=True))
        wait_ready(children[1], f"http://127.0.0.1:{args.web_port}/api/records")
        print(f"준비 완료: http://127.0.0.1:{args.web_port} · 종료: 이 터미널에서 Ctrl+C", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        raise RuntimeError("데모 구성요소가 종료되어 이번 시작 도구의 프로세스들을 정리합니다.")
    except KeyboardInterrupt:
        print("데모 종료 요청. 이번 도구가 시작한 프로세스만 정리합니다.", flush=True)
        return 0
    except (OSError, RuntimeError, KeyError, ValueError, importlib.metadata.PackageNotFoundError) as error:
        print(f"시작 불가: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop(children)
        for log in logs:
            log.close()
        signal.signal(signal.SIGTERM, previous)

if __name__ == "__main__":
    sys.exit(main())
