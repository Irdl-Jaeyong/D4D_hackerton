# D4D NAVIS-AI

D4D T1-1 Multi-UxV Control을 위한 Gazebo 기반 웹 관제 MVP.
관제 대상은 UAV 4대와 USV 2대이며, 함정은 시나리오 중심 대상으로 별도 취급한다.

웹·ROS 구성은 폴더 뼈대 상태다. Ollama 실행 환경은 `docs/ollama.md`를 참고한다.

## 폴더 역할

- `frontend/src/components/`: 상태 카드, AI 채팅, 이벤트 타임라인 등 화면 구성
- `frontend/src/api/`: 웹 백엔드 통신
- `backend/app/`: FastAPI, Ollama/VLM 호출, 명령 검증 및 브릿지 통신
- `ros_ws/src/navis_bridge/`: 상태·카메라 전달 및 명령 수신용 ROS 패키지 예정
- `ros_ws/src/navis_sim/worlds/`: Gazebo 월드
- `ros_ws/src/navis_sim/models/`: 시뮬레이션 모델
- `ros_ws/src/navis_sim/launch/`: 시뮬레이션 실행 설정
- `docker/ros/`: ROS·Gazebo 컨테이너 설정 예정
- `docs/`: 요구사항, 결정 사항, 시연 및 평가 기록
- `scripts/`: 시작·종료 스크립트
- `assets/design/`: 정적 화면 시안

## 구현 전 확인 사항

프론트엔드 도구, ROS·Gazebo 버전, VLM 모델, 시각 입력, 브릿지 통신 방식, Docker 적용 범위는 미정이다.
의존성 파일, ROS 패키지 메타데이터와 Docker 실행 설정은 환경 확인 후 작성한다.
Ollama 모델 파일은 프로젝트에 저장하지 않는다.

## Ollama

설치와 실행 방법: [docs/ollama.md](docs/ollama.md)

개발 PC의 Gazebo·ROS 위치: [docs/environment.md](docs/environment.md)
