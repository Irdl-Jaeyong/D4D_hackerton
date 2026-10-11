> 상황 생성 도구 대신 기존 4종 시나리오를 2분 간격으로 랜덤 생성합니다. 신선한 함선 상태가 수신될 때만 생성하고 대기 4건·종류별 2건·고장 기체 총 6대 제한을 적용합니다. 설정은 `config/auto_scenarios.json`에서 변경할 수 있습니다. 자동 생성은 모의 상황이며, 대응 출동은 운용자의 선택으로만 실행합니다.

> 현재 대시보드에는 위험도 순 승인대기열이 표시됩니다. 상위 2건을 10초마다 갱신하며, 나머지 상황은 보관합니다. 등급 필터와 수동 재계산 버튼은 없으며, 대응안을 선택하면 최신 상태로 재계산한 뒤 Gazebo 대형 변경·UAV/USV 출동을 요청합니다.

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


### AI 대화의 상황 사례 참고

`config/defense_scenarios_200.json`의 가상 사례 200개를 기존 AI 대화에 연결했습니다. 질문의 키워드와 문장 유사도로 관련 사례를 찾고, 현재 통신·배터리·임무 가용 상태를 확인한 배정 엔진이 대응안 세 개를 계산합니다. LLM은 그 결과의 장점과 한계를 설명하며 기체 번호를 결정하지 않습니다. 각 답변에 제안 대형과 배정 기체를 표시합니다.

이는 모델 가중치를 재학습하는 방식이 아니라 요청마다 참고 자료를 제공하는 검색 기반 방식입니다. `DEF-101`처럼 사례 번호를 지정할 수도 있습니다. 사례는 실제 탐지나 고장 진단이 아니며, 질문이 모호하면 출동 대신 확인 방법 세 개를 제시합니다. 좌표가 없으면 도달 시간이나 새 출동 위치를 추측하지 않습니다. 채팅은 임무·대형을 변경하거나 승인하지 않습니다. 모델 연결 또는 출력 검증에 실패하면 사례와 엔진 근거로 답변을 표시합니다.

질문에 정보가 부족하면 채팅이 방향·거리·대상 수 또는 고장 기체 번호를 다시 묻습니다. 같은 입력창에서 답하면 이전 질문과 합쳐 계산하고, `새 상황으로 질문` 버튼으로 문맥을 초기화할 수 있습니다. 위치는 현재 함선 방향을 기준으로 해석하며 좌현은 왼쪽, 우현은 오른쪽입니다. 신고한 위치의 관측 제안에는 기체별 이동 거리와 직선 ETA를 표시합니다. 이는 충돌 회피 경로 또는 실제 운용에서의 안전 이격 거리 검증이 아닙니다.

대화 작성 예시는 `config/chat_examples_600.jsonl`에 저장됩니다. 기존 200개 상황을 정상 자원·정비 제외·자원 부족의 세 조건으로 확장한 600개 대화이며, 각각 추가 질문과 대응안 세 개를 포함합니다. 읽기용 파일은 `outputs/chat_examples_600.txt`, 재생성 명령은 `backend/.venv/bin/python scripts/build_chat_examples.py`입니다. AI 요청에는 해당 상황의 예시 세 개를 답변 형식 참고용으로 전달합니다. 예시의 기체·거리는 합성 데이터이고 현재 배정 결과를 대체하지 않습니다. 동일한 작성 틀을 사용하는 합성 예시이며 전문가 검토나 모델 미세조정을 완료한 데이터셋은 아닙니다.

확장 자료는 `config/chat_examples_1800.jsonl`과 읽기용 `outputs/chat_examples_5400.txt`입니다. 기존 200개 상황 × 자원 조건 3개 × 질문 표현 3개로 질문 1,800개·대응안 5,400개를 구성합니다. 각 대응안에는 확인·배정·계획·승인 전 검토의 네 단계와 보류 조건을 포함합니다. 위치 신고가 바뀐 예시에서는 정정임을 명시합니다. `backend/.venv/bin/python scripts/build_chat_examples_5400.py`로 재생성합니다. AI 참고 예시는 확장 자료를 우선 사용하되 요청마다 정상·정비 제외·자원 부족 예시를 하나씩 전달합니다. 이는 5,400개의 독립 상황이나 전문가 검증 전술이 아닌, 기존 상황의 합성 대화 확장입니다.

웹 문서 기반 추가 질문은 `config/web_faq_60.json` / `outputs/web_faq_60.txt`에 있습니다. 2026-10-10에 확인한 PX4·ArduPilot 운용 문서와 FAA·USCG FAQ 8곳의 주제로 질문 60개·프로젝트 검토 답변 180개를 추가했습니다. 총 자료는 기존 답변 5,400개와 추가 답변 180개입니다. 질문은 프로젝트용 한국어 재작성이며 빈도 순위나 원문 FAQ 그대로가 아닙니다. `source_fact`와 출처 URL은 근거를, 세 대응안은 우리 앱의 제안을 나타냅니다. FAQ는 현재 기체 배정 없이 일반 확인 방법을 설명합니다. 해외 규정을 국내 허가 판단으로 사용하지 않습니다. 채팅에서 관련 FAQ를 찾으면 출처 링크를 표시하며, 현재 통신·배터리 또는 명령 상태를 웹 자료로 대체하지 않습니다. 재생성: `backend/.venv/bin/python scripts/build_web_faq.py`.

FAQ 확장 자료는 `config/faq_situations_600.jsonl` / `outputs/faq_situations_600_answers_6000.txt`입니다. FAQ 60개 각각에 정보 부족·자료 지연·설정 미확인·저잔량·이상 기체·센서 불일치·자원 부족·환경 미확인·회복 재검증·복합 경고의 10개 조건을 적용했습니다. 상황 600개에 각각 확인·자료·설정·배정·대형·정비·시험·사람 판단 등의 검토 관점으로 답변 10개씩, 총 6,000개 답변을 작성했습니다. 답변들은 함께 참고할 수 있는 관점이며 서로 배타적인 실행 전술 열 가지가 아닙니다. 기존 5,580개 답변과 합친 자료 수는 11,580개입니다. AI에는 관련 FAQ의 합성 예시 하나를 참고용으로 전달하며 화면의 추천안 세 개와 사람의 최종 승인은 유지합니다. 예시의 15초 지연·18% 잔량은 합성 조건이며 운용 임계값이 아닙니다. 재생성: `backend/.venv/bin/python scripts/build_faq_situations.py`.

중복 정리

AI는 `config/chat_examples_deduplicated.jsonl`과 `config/faq_situations_deduplicated.jsonl`을 우선 참고합니다. 입력 기체 상태·위치·원래 상황·배정 결과가 모두 같은 대화는 통합하고 질문 표현은 `question_variants`, 원본 ID는 `source_ids`에 보존합니다. FAQ 확장 자료는 같은 주제·조건·답변 묶음을 통합하며 60개 원래 FAQ 모두를 별칭으로 연결합니다. 다른 거리·가용 상태·수행 불가 결과는 합치지 않습니다. 원본 파일은 재생성과 비교용으로 유지합니다.

상황 대화 1,800→900개, FAQ 확장 상황 600→100개, 기본 FAQ 60개를 보존해 검토 기록 총 1,060개·저장 답변 묶음 3,880개로 정리했습니다. `config/training_review_deduplicated.jsonl`은 원문 구조를 포함하는 검토용 자료이며 모델 학습 파일 형식 변환·학습 실행은 별도입니다. 읽기용은 `outputs/training_review_deduplicated.txt`, 집계는 `outputs/deduplication_report.json`입니다. 의미가 비슷하다는 이유만으로 자동 통합하거나 모든 반복 문구가 사라졌다고 판단하지 않습니다. 재생성: `backend/.venv/bin/python scripts/deduplicate_chat_data.py`.

대표 50개 자료 검토와 평가 분리

`backend/.venv/bin/python scripts/review_and_split_data.py`는 상황 범주 20개에서 정상·자원 부족 각 한 사례와 FAQ 주제 10개에서 한 사례를 골라 내용 검토 결과를 생성합니다. `config/training/representative_review_50.json`과 `outputs/representative_review_50.txt`에 사례별 확인한 점·수정 사항을 기록했습니다. 전문가 검증이나 모델 성능 평가가 아니며 50개 모두 수정 필요로 표시했습니다. 특히 같은 관측 좌표를 공유하는 복수 UAV 계획, 미확인 정보가 남았는데 끝나는 대화, 질문에 직접 답하지 않는 일반 FAQ 답변, 점검 관점 10개와 추천안 3개의 형식 차이가 남아 있습니다.

분할은 `config/training/train_candidates.jsonl` 828개, `validation_candidates.jsonl` 108개, `test_candidates.jsonl` 124개입니다. 원래 상황 ID·FAQ 별칭·주제 가족을 묶어 분리했습니다. `split_manifest.json`에서 중복 및 누락 검사를 확인할 수 있습니다. 이것은 검토용 구조의 후보 자료이며 바로 미세조정 도구에 넣는 학습 파일이 아닙니다. 학습 가능 승인 또는 학습 실행을 뜻하지 않습니다.

평가용 참고 자료는 `config/training/train_reference_catalog.json`이며 학습 분할의 사례·FAQ·출처만 담습니다. 운영 채팅은 기존 전체 자료를 계속 참고하므로 그 API를 그대로 최종 평가에 사용하면 평가 자료 누출이 발생합니다. 별도 오프라인 평가에서 필터된 참조만 사용해야 합니다. `evaluation_rubric.json`은 재질문·엔진 배정 준수·대응안 구분·불확실성·실행 경계·운용자 설명의 여섯 항목을 제안합니다. 모델 성능 점수는 아직 측정하지 않았습니다.

KOYUL의 기존 사례 기반 대화는 `/api/chat/scenario`에 보존합니다. 현재 관제 화면은 최신 상태 기반 `/api/chat`을 사용합니다.

## 이 PC에서 고율 최신 버전 실행

```bash
D4D_enter
D4D_enter status
D4D_enter logs
D4D_enter stop
```

웹 주소: http://127.0.0.1:18083/ . `scripts/D4D_enter.sh`가 Ollama 모델 설치, 웹 준비, 전체 기체 상태와 영상 수신을 확인하고 Gazebo GUI를 엽니다. 로컬 `.env`에서 포트·모델·서비스·컨테이너를 설정합니다. 종료 시 공유 Ollama는 유지합니다.
