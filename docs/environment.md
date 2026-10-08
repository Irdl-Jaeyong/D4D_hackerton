# 개발 PC 환경 조사

확인일: 2026-10-09 한국시간. 호스트 명령, 설치 패키지, Docker 이미지와 마운트를 직접 확인했다.
기존 프로젝트 컨테이너를 시작하거나 수정하지 않았으며, 이미지 검사는 마운트·네트워크 없이 임시 컨테이너로 수행하고 종료 후 삭제했다.

## 호스트

- OS: Ubuntu 24.04.5 LTS, x86_64
- GPU: NVIDIA GeForce RTX 5080 Laptop GPU, 16303 MiB, 드라이버 580.178.04
- Gazebo 명령: `/usr/bin/gz`, 실행 명령 `gz sim`
- Gazebo Sim 버전: 8.15.0
- Gazebo 라이브러리: `/usr/lib/x86_64-linux-gnu/`, 플러그인 디렉터리 `/usr/lib/x86_64-linux-gnu/gz-sim-8/`
- 기본 월드: `/usr/share/gz/gz-sim8/worlds/`
- 사용자 Gazebo 데이터: `/home/jang/.gz/`
- 호스트 `/opt/ros` 및 PATH의 `ros2` 없음. 확인한 범위에서 호스트 ROS 설치를 찾지 못함.

## 기존 Docker 환경

| 이미지 | ROS 경로 | Gazebo | 브릿지 |
| --- | --- | --- | --- |
| `aac-2026-image:sim` | `/opt/ros/humble` | `ign gazebo`, 6.18.0 | `ros_gz_bridge`, `ros_gz_sim` 설치 확인 |
| `aac-2026-image:x86` | `/opt/ros/humble` | `ign gazebo`, 6.18.0 | `ros_gz_bridge`, `ros_gz_sim` 설치 확인 |

ROS 실행 파일은 두 이미지 모두 `/opt/ros/humble/bin/ros2`다. 사용 전 `source /opt/ros/humble/setup.bash`가 필요하다.
호스트 Gazebo 8과 기존 컨테이너 Gazebo 6을 동일한 버전으로 취급하지 않는다. 서로 연결되는지는 아직 검증하지 않았다.

### 컨테이너와 워크스페이스

- `f1tenth-sim-dev`: 조사 당시 종료 상태. `aac-2026-image:sim`과 같은 이미지 ID 사용.
  - 호스트 `/home/jang/irdl_ws/f1tenth/src/aac_2026` → 컨테이너 `/ros_ws/src/aac_2026`
  - `/ros_ws/build`, `/ros_ws/install`, `/ros_ws/log`는 Docker 볼륨.
- `aac-2026-container-all`: 조사 당시 종료 상태. `aac-2026-image:x86` 사용.
  - 호스트 `/home/jang/irdl_ws/f1tenth` → 컨테이너 `/ros_ws`
- `isaac-lab-base`: 조사 당시 실행 중. `/opt/ros`와 PATH의 `ros2`, `gz`, `gazebo`는 확인되지 않음. D4D용으로 변경하지 않음.
- `/home/jang/ros_ws`도 존재하지만 이번 프로젝트 작업 위치는 아님.

## 기존 소스와 에셋

- ROS 튜토리얼: `/home/jang/irdl_ws/src/irdl_tutorial`
- 해당 Docker 설정: `/home/jang/irdl_ws/src/irdl_tutorial/docker`
- 기존 F1TENTH ROS 소스: `/home/jang/irdl_ws/f1tenth/src/aac_2026`
- 기존 Gazebo 트랙 소스: `/home/jang/irdl_ws/f1tenth/src/aac_2026/system/simple_gazebo_track`
- PX4 Gazebo 모델: `/home/jang/irdl_ws/opt/px4-gz-models`

## D4D 적용 판단

Ollama는 호스트에서 유지한다. 기존 ROS 환경을 재사용하려면 ROS·Gazebo 6·브릿지를 같은 컨테이너 환경에 두는 구성을 우선 검토할 수 있다.
호스트 Gazebo 8을 사용하려면 이에 맞는 ROS·브릿지 환경을 별도로 선정하고 검증해야 한다.
현재 D4D의 시뮬레이터 실행, ROS 토픽, 카메라, 웹 연동은 검증 전이며 Docker 적용도 확정하지 않았다.

Ollama 설치·모델 경로는 [ollama.md](ollama.md)를 참고한다.

## 후속 검증

호스트 Gazebo GUI와 VLM 동시 실행·카메라 입력 검증: [gazebo_vlm_test.md](gazebo_vlm_test.md). ROS 및 다중 기체 연동은 아직 미검증.
