# NAVIS-AI · D4D Hackathon

한 운용자가 여러 이기종 UxV를 관제하는 Gazebo 기반 웹 MVP.
현재 **메인 함선 1척 + UAV 40대 + 호위 USV 10대**를 Gazebo 해상 월드에 호위 편대로 배치하고 실제 위치·높이·속도를 웹에 연결했다. 카메라는 전체 함대를 위에서 비스듬히 내려다보는 1280×720 Gazebo 관측 센서다.
드론 40대 전부가 메인 함선 위 반지름 52m의 반구 대형을 이루고, 호위 USV 10대가 주변 경계를 따라 이동한다.
로컬 선체 메시, 함교·마스트·레이더·갑판과 쿼드콥터 형상을 사용한다. 바다는 시각 표현이며 부력·파도 물리·비행·항해 제어·AI 행동 실행은 아직 구현 전이다. 사진 수준의 실사 환경은 아니다.

## 현재 기능

- 웹 관제: 51대 상태 카드, 실시간 카메라, ROS 위치를 표시하는 2D 지도, 연결 이벤트, 채팅
- FastAPI: 현재 상태 조회, 카메라 JPEG, MiniCPM-V 4.5 텍스트·이미지 요청
- Gazebo 6 + ROS 2 Humble: odometry·카메라 → ros_gz_bridge → ROS 노드 → 백엔드
- 실제 데이터가 없는 기체는 미연결 표시. 배터리는 구현되지 않아 수치를 표시하지 않는다.
- 데이터 수신이 5초 이상 끊기면 연결 해제하고 카메라 분석을 차단한다.
- **모델 응답으로 이동 명령을 실행하지 않는다.**

## 이 PC에서 시작

시뮬레이션은 로컬 `aac-2026-image:sim` 또는 `aac-2026-image:x86` Docker 이미지를 사용한다. `prep.sh start`로 전체 스택을 시작하려면 Ollama와 모델도 설치되어 있어야 한다. 이 PC에서는 현재 웹·시뮬레이션만 실행 중이다.

```bash
cd /home/jji/D4D_hackerton
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
3. ROS 2 Humble, Gazebo Fortress, ros_gz_bridge, rclpy, OpenCV, NumPy를 포함하는 Docker 이미지가 필요하다. 사용하는 `aac-2026-image:sim` / `aac-2026-image:x86`은 기존 로컬 이미지이며 일반 Docker Hub 이미지가 아니다.
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

## 함대 월드 구성

`config/fleet.json`에 함정·드론·USV 수를 정의한다. 현재 1 / 40 / 10이다.

```bash
python3 scripts/build_fleet.py
./scripts/prep.sh stop
./scripts/prep.sh start
./scripts/open_gazebo.sh
```

월드 생성기는 로컬 함선 에셋과 Apache-2.0 [VRX](https://github.com/osrf/vrx)의 바다 메시·법선 텍스처로 `prep.sdf`를 생성한다. 생성된 월드는 Git에 포함하므로 재생성 없이 실행 가능하다. UAV는 위치 갱신 기반 편대 시연용 모델이며 기존 X3 비행 예제와 다르다. GUI에서 마우스로 3D 시점을 조작할 수 있고, 웹은 함선을 추적하는 항공 카메라 스트림을 표시한다. GUI 시점 변경은 웹 카메라 시점에 적용되지 않는다.

Gazebo 월드가 준비된 뒤 ROS 브릿지를 시작하며, 상태 수신기는 13대씩 분할한다. 카메라 영상은 `SHIP-01` 상태 업로드를 통해 전달되지만 실제 센서는 함정에 달린 카메라가 아닌 `fleet_observer`다. Ollama가 없으면 AI 대화는 사용할 수 없다.

## 직선 전진, 반구 대형과 8자 순찰

`convoy_motion.py`는 ROS `/clock`의 시뮬레이션 시간을 기준으로 움직인다. 메인 함선은 1.5m/s로 직선 전진하고, USV는 함선 상대 x=48m/y=32m의 타원형 경계를 따라 연속적으로 호위 위치를 교대한다. 멈춤·급출발 없이 선행 함선 위치를 기준으로 이동한다.

드론 40대는 반지름 52m, 중심 높이 12m인 반구 표면에 배치한다. 위도 12°/26°/40°/54°/68°의 다섯 고도 편대에 8대씩 속하며, 각 드론은 38초 주기의 작은 8자 경로를 반구 표면에서 비행한다. 고도 편대는 서로 다른 방향으로 천천히 교대한다. 갑판 대기 드론은 없다.

8자 경로는 [ModalAI VOXL의 실제 Offboard 예제](https://docs.modalai.com/voxl-figure-8/)와 [PX4 개발 키트 비행 튜토리얼](https://px4.io/first-flight-tutorial-for-the-voxl-2-based-px4-autonomy-developer-kit/)의 패턴을 참고했다. USV의 선행 함선 상대 오프셋은 [ArduPilot Follow Mode](https://ardupilot.org/rover/docs/follow-mode.html)를 참고했다. 반구 표면으로의 변환과 다중 기체 교대는 이 프로젝트의 시연 설계이며 실제 작전 대형이라고 주장하지 않는다.

Gazebo `set_pose_vector`로 위치를 갱신하는 시연이다. PX4·ArduPilot 비행 제어기, 추진력·부력·충돌 회피·위협 대응은 실행하지 않는다. 속도는 ROS 위치의 시뮬레이션 시간별 변화로 추정한다. AI는 움직임을 제어하지 않는다.

배가 가려지던 바다 메시의 높이 변형을 제거했다. 바다는 선체보다 낮은 평평한 원본 VRX 메시와 법선 텍스처를 사용하고 함선을 따라 중심을 갱신한다. 웹 카메라와 Gazebo GUI가 함선을 따라가며, 웹에서는 반구 가이드와 실제 위치를 겹쳐 볼 수 있다. 카메라는 전체 편대가 프레임 안에 들어오는 범위를 사용한다. IGN_PARTITION은 `navis-d4d-koyul`이다.

```bash
python3 tests/test_convoy_geometry.py
python3 scripts/check_prep.py
```

첫 검사는 반구 유지, 드론 간 거리, 카메라 경계, 수면 높이, 경로 연속성을 확인한다. 두 번째 검사는 실행 중인 웹·51대 상태·JPEG·API 입력 검증을 확인하며 Ollama 모델이 없으면 AI 응답 검사를 생략한다.
