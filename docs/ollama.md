# Ollama 실행 환경

## 배치

Ollama는 호스트의 사용자 전용 경로에 설치한다. 웹 백엔드와 ROS 패키지에 바이너리나 모델을 포함하지 않는다.

- 런타임: `~/.local/share/ollama-runtime/` (`XDG_DATA_HOME` 설정 시 해당 경로 아래)
- 모델: `~/.local/share/ollama/models/`
- 프로젝트 설정: `.env.example`의 `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
- API 주소: `http://127.0.0.1:11434`
- 실행 관리: `scripts/ollama_service.sh`

## 설치와 실행

프로젝트 루트에서 실행한다.

```bash
./scripts/install_ollama.sh
./scripts/ollama_service.sh start
./scripts/ollama.sh --version
curl --fail http://127.0.0.1:11434/api/version
./scripts/ollama.sh list
```

설치 스크립트는 공식 Linux 배포 파일을 내려받고 관리자 권한 없이 사용자 경로에 압축을 해제한다.
기본 설치 버전은 `0.40.1`로 고정했다. 다른 버전은 `OLLAMA_VERSION` 환경변수로 지정할 수 있다.
현재 설치가 있는 상태에서 재설치할 때는 먼저 서비스를 종료한다.

```bash
./scripts/ollama_service.sh stop
OLLAMA_VERSION=0.40.1 ./scripts/install_ollama.sh
./scripts/ollama_service.sh start
```

사용자 systemd 서비스로 실행하며 부팅 자동 시작은 등록하지 않는다. 다음 로그인 후에는 `start`를 실행한다.
서비스 로그는 `./scripts/ollama_service.sh logs`로 확인한다.
systemd 사용자 서비스를 사용할 수 없는 환경에서는 `./scripts/ollama.sh serve`를 터미널에서 실행한다.

## 모델

MiniCPM-V 4.5를 시험 후보로 다운로드했다. 이미지 추론 속도·GPU 사용 검증과 최종 모델 확정은 후속 작업이다.
선정 후 아래 명령의 `<모델명>`을 실제 모델명으로 바꿔 실행하고 `.env`의 `OLLAMA_MODEL`에도 기록한다.
`.env`를 읽는 백엔드는 아직 구현되지 않았다.

```bash
./scripts/ollama.sh pull <모델명>
```

## 백엔드 연결

`frontend → backend → Ollama` 순서로 호출한다. Gazebo 상태와 이미지는 ROS 브릿지를 통해 백엔드에 전달한다.
현재 Ollama API는 호스트 내부에서만 접근하도록 설정했다.
백엔드를 컨테이너로 옮길 때는 컨테이너 네트워크와 주소 설정을 별도로 조정해야 한다.

## 참고

공식 Linux 설치 문서: https://docs.ollama.com/linux

## 설치 확인 결과 (2026-10-09 한국시간)

- 설치 버전: `0.40.1`
- 사용자 서비스 `d4d-ollama.service`: 실행 중
- `/api/version`: HTTP 200, 버전 확인 완료
- `/api/tags`: HTTP 200, 모델 목록은 비어 있음
- 서버 로그에서 RTX 5080 Laptop GPU의 CUDA 인식 확인
- 모델 추론과 응답 속도는 아직 측정하지 않음

## MiniCPM-V 4.5 다운로드 결과

- 모델: `minicpm-v4.5:latest`
- 크기: 6121827879 bytes (약 6.1GB)
- digest: `0c40168f46d1cbf5cec399d8ced34b6d3347a79f69306866efa44203c08eeda3`
- 저장 루트: `/home/jang/.local/share/ollama/models/`
- API 모델 목록 등록과 SHA256 검증 완료
- 텍스트·이미지 추론 실행 완료. 결과와 한계: [vlm_test.md](vlm_test.md)

실행: `./scripts/ollama.sh run minicpm-v4.5:latest`

## 현재 AI 대화 연결
준석 시츄에이션 화면은 `scripts/llm_dialogue.py`를 통해 `/api/chat`를 실제 호출합니다. 기본 설치 예시는 Qwen3 4B입니다. 런타임 설치 후 `scripts/ollama_service.sh start`, `scripts/ollama.sh pull qwen3:4b`를 실행하고 `.env`에 `OLLAMA_MODEL=qwen3:4b`를 설정합니다. 백엔드 재시작 후 `/api/health`에서 모델 설치 상태를 확인하세요.

이 모델은 텍스트 상태·검색된 사례 기반 설명에 사용합니다. 카메라 이미지 분석은 미연결입니다. 데이터셋을 모델 가중치에 학습시킨 것이 아니라 질문마다 관련 근거를 제공하는 구조입니다. 상태·판정·명령은 기존 엔진이 관리하며 LLM은 설명만 작성합니다. 모델 연결 또는 응답 형식 검증 실패 시 규칙 답변으로 돌아가고 화면에 LLM 사용 안 함을 표시합니다. 답변 검증은 형식·수치·일부 실행 주장 검증이며 모든 환각을 차단한다는 보장은 없습니다.
