# NAVIS-AI · D4D Hackathon

한 운용자가 여러 이기종 UxV를 관제하는 Gazebo 기반 웹 MVP.
현재 **UAV 4대 + USV 2대의 실제 위치·높이·속도**를 웹에 연결했고, USV-01 카메라와 MiniCPM-V 채팅을 제공한다. UAV 4대는 함정 갑판에 배치했다. 안정적인 비행·항해 제어와 AI 행동 실행은 아직 구현 전이다.
중심 함정은 정적 저폴리곤 모델로 표시한다. 다중 기체 임무, 자연어 행동 실행과 해상 물리는 아직 구현하지 않았다.

## 현재 기능

- 웹 관제: 6대 상태 카드, 실시간 카메라, ROS 위치를 표시하는 2D 지도, 연결 이벤트, 채팅
- FastAPI: 현재 상태 조회, 카메라 JPEG, MiniCPM-V 4.5 텍스트·이미지 요청
- Gazebo 6 + ROS 2 Humble: odometry·카메라 → ros_gz_bridge → ROS 노드 → 백엔드
- 실제 데이터가 없는 기체는 미연결 표시. 배터리는 구현되지 않아 수치를 표시하지 않는다.
- 데이터 수신이 5초 이상 끊기면 연결 해제하고 카메라 분석을 차단한다.
- **모델 응답으로 이동 명령을 실행하지 않는다.**

## 이 PC에서 시작

Ollama와 모델, `aac-2026-image:sim` Docker 이미지가 설치된 현재 PC 기준이다.

```bash
cd /home/jang/irdl_ws/D4D_Hackerton
./scripts/setup_backend.sh   # 첫 설치 또는 의존성 갱신 시
./scripts/prep.sh start
```

브라우저에서 **http://127.0.0.1:8000**을 연다. 별도 Gazebo 창이 필요하면 GUI가 있는 터미널에서 `./scripts/open_gazebo.sh`를 실행한다 (GUI 프로세스 실행 확인, 브라우저·GUI의 실제 클릭 검수는 남아 있음). 자동 실행 서비스는 현재 로그인 세션에서만 시작하며 부팅 자동 시작은 등록하지 않는다.

```bash
./scripts/prep.sh status
./scripts/prep.sh stop       # 웹·시뮬레이션 종료, Ollama는 유지
./scripts/ollama_service.sh stop  # Ollama까지 종료하려는 경우
```

서비스 없는 환경에서는 터미널 두 개에서 `./scripts/start_backend.sh`, `./scripts/start_sim.sh`를 각각 실행한다.

## 처음 준비하는 PC

1. Python 3.12와 venv, Docker + NVIDIA Container Toolkit을 준비한다.
2. [Ollama 안내](docs/ollama.md)에 따라 런타임과 `minicpm-v4.5:latest`를 설치한다.
3. ROS 2 Humble, Gazebo Fortress, ros_gz_bridge, rclpy, OpenCV, NumPy를 포함하는 Docker 이미지가 필요하다. 현재 사용 중인 `aac-2026-image:sim`은 이 PC의 기존 이미지이며 일반 Docker Hub 이미지가 아니다.
4. 호환되는 다른 이미지를 쓰면 `.env`의 `NAVIS_ROS_IMAGE`를 설정한다. 다른 PC에서의 재현은 아직 검증하지 않았다.
5. `setup_backend.sh`는 `.env`가 없을 때만 로컬 브릿지 토큰을 생성한다. 실제 `.env`는 Git에 올리지 않는다.

## 구조

- `frontend/`: 빌드 도구 없는 HTML/CSS/JS 관제 화면
- `backend/app/main.py`: 웹 API와 Ollama 호출 (가상환경은 `backend/.venv`)
- `ros_ws/src/navis_bridge/`: 읽기 전용 ROS 텔레메트리 노드
- `ros_ws/src/navis_sim/`: 로컬 에셋만 사용하는 준비용 월드·ROS launch
- `docker/ros/run_prep.sh`: 기존 ROS 이미지에서 시뮬레이션·브릿지 실행
- `scripts/`: 설치, 시작·종료, 검증
- `docs/`: 실행 환경과 테스트 기록
- `outputs/`: 로컬 테스트 결과 (Git 제외)

## 검증과 한계

```bash
python3 scripts/check_prep.py
```

검증 결과와 다음 단계: [준비용 MVP 상태](docs/preparation.md).
기존 환경: [environment.md](docs/environment.md). 모델 테스트: [vlm_test.md](docs/vlm_test.md), [gazebo_vlm_test.md](docs/gazebo_vlm_test.md).

최종 과제와 사전 코드 허용 범위는 주최 측 확인이 필요하다. 모델의 화면 해석에는 오류가 발생할 수 있으며 이번 구현으로 인지 부하 감소나 임무 성공률을 검증한 것은 아니다.

## X3 쿼드콥터 에셋

공식 Gazebo 예제의 OpenRobotics X3 UAV 버전 4를 사용한다. 처음 준비하는 PC에서는 `./scripts/install_uav_example.sh`로 다운로드·월드 추가를 수행한다. 모델은 `ros_ws/src/navis_sim/models/x3_uav/`에 저장되며 Git에서 제외된다. 추가 스크립트는 `scripts/add_quadcopter.py`다.

## 현재 6대 상태 연동

UAV-01~04와 USV-01~02 총 6대를 해상 월드에 배치하고 실제 ROS odometry를 웹 상태 카드에 연결했다. 위치 x/y/z와 속도를 표시하며 배터리는 미구현이다. UAV는 갑판에 대기하고 있고 비행/항해 제어 및 AI 행동 실행은 아직 없다. 카메라는 USV-01만 제공한다.
