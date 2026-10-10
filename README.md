> 상황 생성 도구 대신 기존 4종 시나리오를 2분 간격으로 랜덤 생성합니다. 신선한 함선 상태가 수신될 때만 생성하고 대기 4건·종류별 2건·고장 기체 총 6대 제한을 적용합니다. 설정은 `config/auto_scenarios.json`에서 변경할 수 있습니다. 자동 생성은 모의 상황이며, 대응 출동은 운용자의 선택으로만 실행합니다.

> 현재 대시보드에는 위험도 순 승인대기열이 표시됩니다. 상위 3건을 10초마다 갱신하며, 나머지 상황은 보관합니다. 등급 필터와 수동 재계산 버튼은 없으며, 대응안을 선택하면 최신 상태로 재계산한 뒤 Gazebo 대형 변경·UAV/USV 출동을 요청합니다.

# JCC · NAVIS-AI

Gazebo 해상 시뮬레이션과 웹 관제 화면을 연결하는 D4D MVP입니다. 준석 `work/junseok-situation-queue`의 Gazebo·백엔드 코드에 간소화한 관제 화면을 통합했습니다.

## 현재 화면과 데이터

- 왼쪽: 기체 검색, UAV/USV 필터, 기체 목록과 모의 배터리 잔량.
- 중앙: 실제 Gazebo 센서 영상, ROS odometry 기반 위치 모니터, 선택 기체 월드 좌표.
- 오른쪽: 선택 기체의 연결·높이·속도·모의 배터리·남은 운용 시간과 AI 대화.
- 상세 설정: 대형 변경, 위험 확인, 상황 생성·추천 갱신, 대응 검토·최종 승인, 모의 고장 시험.
- 이벤트 타임라인은 기본 화면에서 제거했습니다.

기본 구성은 SHIP 1척, UAV 40대, USV 10대입니다. 속도는 위치 변화로 추정하며, 배터리와 운용 시간은 실제 센서값이 아닌 모의 값입니다. 연결이 끊기면 현재 위치·속도·배터리를 확인 불가로 표시합니다.

데이터 경로는 `Gazebo → ros_gz_bridge → ROS 수신 노드 → FastAPI → 웹`입니다. 대형과 승인된 임무는 `웹 → FastAPI → 시뮬레이션 실행 노드 → Gazebo`로 전달합니다. 웹 센서 영상과 native Gazebo 창은 같은 월드를 사용하며, 카메라 시점은 서로 다를 수 있습니다.

준석 브랜치의 상황 큐·상황 모델 생성·고장 종류별 동작·USV 출동 코드를 포함합니다. 간소화한 웹의 대응 콘솔은 현재 실행 중인 임무 또는 우선순위가 가장 높은 대기 상황 한 건을 표시합니다. 전체 큐를 개별 선택하는 화면은 추가 연동이 필요합니다. 현재 UI에서는 대응안 선택 후 **최종 승인**을 눌러 실행합니다.

AI 대화는 MiniCPM-V 4.5의 텍스트·이미지 설명 기능입니다. 자유로운 채팅으로 이동 명령을 실행하지 않습니다. USV는 추진력 기반 물리 모델, 함선과 UAV는 위치 갱신 기반 시연입니다. 실기체 제어·비행 제어기·실측 배터리·경로 안전성 검증은 포함하지 않습니다.

## 실행

Python 가상환경, Ollama와 모델, Docker와 NVIDIA Container Toolkit, ROS 2 Humble / Gazebo Fortress / ros_gz_bridge를 포함하는 로컬 Docker 이미지가 필요합니다. `aac-2026-image:sim`은 이 PC의 기존 이미지이며 공개 Docker Hub 이미지가 아닙니다.

```bash
./scripts/setup_backend.sh
# 생성된 .env에서 모델, 브리지 토큰, Docker 이미지와 아래 연결 설정을 확인
./scripts/prep.sh start
./scripts/open_gazebo.sh
```

기본 주소는 **http://127.0.0.1:18082/**입니다. 종료·상태 확인:

```bash
./scripts/prep.sh status
./scripts/prep.sh stop
```

서비스를 쓰지 않으면 두 터미널에서 `scripts/start_backend.sh`와 `scripts/start_sim.sh`를 실행합니다. native 창은 `scripts/open_gazebo.sh`로 엽니다. 현재 로그인 세션의 서비스이며 부팅 자동 시작은 별도 설정이 필요합니다.

`.env.example`의 실행 설정:

| 설정 | 기본값 | 용도 |
| --- | --- | --- |
| `NAVIS_WEB_PORT` | `18082` | 웹 서버 포트 |
| `NAVIS_BACKEND_URL` | `http://127.0.0.1:18082` | 모든 시뮬레이션 브리지의 접속 주소 |
| `IGN_PARTITION` | `navis-d4d` | 서버·GUI·상황/상태/고장 브리지의 공통 Gazebo 파티션 |
| `ROS_DOMAIN_ID` | `45` | ROS 통신 도메인 |

포트를 바꿀 때는 `NAVIS_WEB_PORT`와 `NAVIS_BACKEND_URL`을 함께 바꿉니다. 서비스 이름을 따로 쓰는 환경에서는 `NAVIS_BACKEND_UNIT`, `NAVIS_SIM_UNIT`도 설정할 수 있습니다. GUI 환경의 `DISPLAY`와 `XAUTHORITY`는 실행 세션에서 전달합니다. 인증정보가 든 `.env`, 가상환경, 모델 다운로드, `outputs/`는 Git에 올리지 않습니다.

## 코드 위치

- `frontend/`: 현재 18082 관제 화면.
- `backend/app/main.py`: 상태·상황 큐·대응 승인·카메라·Ollama API.
- `ros_ws/src/navis_sim/worlds/prep.sdf`: Gazebo 월드.
- `ros_ws/src/navis_bridge/telemetry_node.py`: 위치와 영상 업로드.
- `scripts/convoy_motion.py`, `scripts/mission_execution.py`: 대형과 승인된 임무의 시뮬레이션 실행.
- `scripts/gazebo_*_bridge.py`: 상태·상황·고장 표시와 Gazebo 연동.
- `docker/ros/run_prep.sh`: 시뮬레이터와 ROS 브리지 시작.
- `config/fleet.json`: 기체 수·대형·카메라 구성.

## 확인

```bash
backend/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_queue_state.js
python3 scripts/check_prep.py
```

`check_prep.py`는 실행 중인 웹·텔레메트리·영상·모델을 확인합니다. 별도 주소에서는 `NAVIS_BACKEND_URL`을 전달합니다. 자동 시험은 실제 화면이나 모든 모델 응답의 정확성을 보장하지 않습니다. 인지 부하 감소·임무 성과는 아직 비교 측정 전입니다.

## 에셋과 기존 기록

함선은 [NPS SAVAGE Arleigh Burke](https://savage.nps.edu/Savage/ShipsMilitary/DDGArleighBurkeUnitedStates/)의 공개 모델, USV와 바다 표현은 [Open Robotics VRX](https://github.com/osrf/vrx)의 에셋과 시각 코드를 사용합니다. 원본 라이선스·변경 사항은 모델 디렉터리와 `docker/visual/ATTRIBUTION.md`에 보관합니다. 공개 형상을 사용한 시연이며 실측 디지털 트윈은 아닙니다.

설치·모델 참고: [Ollama 안내](docs/ollama.md), [기존 준비 기록](docs/preparation.md). 기존 기록은 당시 상태를 설명하며 현재 화면·포트와 다를 수 있습니다. `record-explainer-v2/`는 이전 기록 대시보드 소스로, 현재 18082에서 실행하지 않습니다.

## 빠른 대형 전환 시연

현재 로컬 시연은 `config/fleet.json`의 `motion.formation_transition_multiplier=5`로 UAV와 USV 목표 대형 전환 시간을 가속합니다. 전환 계산은 작은 시간 간격으로 나누어 기존 경로와 속도 변화의 연속성을 유지합니다. 함선의 전진 속도와 고장 복귀 계산은 그대로입니다. USV는 `prep.sdf`의 `formation_speed_multiplier=5`를 읽어 정상 상태의 목표 추종 속도·조향·추진 한도를 함께 높입니다. 이는 빠른 시뮬레이션 시연용 설정이며 실제 WAM-V 성능 제원을 뜻하지 않습니다. 물리적 추종과 혼잡에 따라 실제 전환 완료 시간이 정확히 다섯 배 줄지는 않을 수 있습니다. 기본 속도로 복원하려면 두 설정을 모두 1로 바꾸고 시뮬레이터를 재시작합니다.

### 기체 상태와 AI 설명
현재 상태 요약은 모든 기체에 공통 적용됩니다. 방어중(초록), 대기·복귀(파랑), 수행불가(빨강)를 선택 기체 패널에서 현재 임무·판정 근거와 함께 표시합니다. AI 대화에서 `USV-01 왜 방어중이야?`, `UAV-01 뭐 하고 있어?`는 상태 설명 하나를 반환하고, `지금 위험 상황에 어떻게 대응해?`는 현재 통신 지연·고장·잔량·자세·기체 간격 신호를 근거로 안전 검토안 세 가지를 반환합니다. 근거가 부족하면 재질문합니다. 대화는 명령이나 승인 상태를 변경하지 않습니다.

이 기능은 학습 완료된 모델이 아니라 규칙·자료 검색 기반입니다. 준비된 합성 사례를 실제 사고 발생 빈도나 고장 진단으로 취급하지 않으며, 시뮬레이션 임계값은 실제 기체의 운용 한계가 아닙니다. 모든 가능한 상황을 포함했다는 보장은 없습니다.

### 로컬 LLM 대화
Ollama에서 `qwen3:4b`를 실행하면 AI 대화가 실제 모델을 호출합니다. 기체 상태·관련 사례를 질문마다 전달하고 모델은 설명 문장을 생성합니다. 화면 하단에 `실제 LLM · 모델명` 또는 `규칙 답변 · LLM 사용 안 함`이 표시됩니다. 고장 원인이나 수치의 정확성을 모델 학습만으로 보장하지 않으며, 상태 근거는 시스템이 별도로 표시합니다. 가중치 미세조정과 카메라 추론은 이번 연결에 포함되지 않습니다. 설치·실행 방법은 [Ollama 문서](docs/ollama.md)를 참고하세요.

### 다섯 가지 질문 유형
AI 대화는 상태, 판정 이유, 위험 확인, 안전 대응, 복귀·재개 조건의 다섯 유형으로 나뉩니다. `config/training/intent_train.jsonl`의 질문 예시를 수정하고 `backend/.venv/bin/python scripts/question_intents.py`를 실행하면 질문 분류 모델이 재학습됩니다. 평가 결과는 `config/training/intent_evaluation.json`에 기록됩니다. 이는 Qwen 가중치 미세조정이 아닙니다. 현재 분류기는 실험적 소규모 모델이므로 명확한 표현을 우선하고 매우 높은 신뢰도의 분류만 라우팅에 사용합니다. 숫자나 유형 판정이 실제 정확도를 보장하지 않습니다.
