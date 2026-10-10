# 출발 전 준비용 MVP

2026-10-09 한국시간.

## 완료 범위

웹 프론트엔드, FastAPI, Ollama, Gazebo, ROS 사이에 상태·카메라·대화 흐름을 연결했다.
호스트에는 Python 백엔드와 Ollama를 실행하고, 별도 `d4d-navis-prep` 컨테이너에 기존 `aac-2026-image:sim` 이미지를 활용한다.
기존 F1TENTH 컨테이너와 소스, tilt 작업은 변경하지 않았다.

- Gazebo 6.18.0 / ROS 2 Humble을 같은 컨테이너에서 사용
- 시뮬레이션 격리: IGN_PARTITION=navis-d4d-prep, ROS_DOMAIN_ID=44
- USV-01은 단순 상자 형태의 준비용 모델. 지면 위에서 상태·카메라 전송 확인에 사용한다. 해상 운동·선박 물리·자율항해는 구현하지 않았다.
- 카메라: 640×480, Gazebo 센서 10Hz, 웹 전송 약 1Hz
- 위치: /navis/odometry → ROS nav_msgs/Odometry → 백엔드 약 5Hz
- 웹: 상태를 1초 간격으로 조회, 수신 중단 5초 뒤 미연결 판정
- UAV 4대와 USV-02는 미연결 표시
- 배터리 센서·함정·임무 실행·기체 이동 제어 없음
- 브릿지 업로드는 로컬 토큰 인증. 서버는 127.0.0.1에만 바인딩.

## 검증

- navis_bridge·navis_sim: 컨테이너 내 colcon build 성공
- 프론트엔드 HTML/JS 제공 HTTP 200, 백엔드 /api/health 정상
- 실제 ROS 토픽 /navis/<vehicle>/odometry, /navis/camera/wide, /navis/camera/detail 수신 확인
- /api/state에서 USV-01만 연결, 나머지 5대 미연결 확인
- /api/camera의 실제 렌더링 JPEG 확인: 왼쪽 녹색 구, 오른쪽 빨간 상자
- Gazebo set_pose 서비스로 모델 위치를 (2,1)로 변경한 뒤 백엔드 좌표도 (2,1)로 갱신되는 것을 검증. 테스트 후 원래 위치로 복원.
- 내부 업로드의 인증 없는 요청 HTTP 403, 빈 채팅 HTTP 422 확인
- 시뮬레이션 종료 뒤 미연결·카메라 HTTP 503·오래된 이미지 채팅 HTTP 409 확인, 이후 재시작
- 실제 Ollama 채팅: 전체 6대 연결 상태 나열 약 0.83초, 카메라 설명 약 0.88초, 미지원 이동 요청 답변 약 0.89초
- 카메라 설명: 왼쪽 녹색 구, 오른쪽 빨간 사각형으로 답변
- 이동 요청: 실행할 수 없다고 답변하고 API executed=false 반환

시간은 단일 로컬 요청의 관측값이며 모델이 이미 로드된 상태다. 재실행·다중 사용자·복잡한 화면 성능을 보장하지 않는다.
상태 요약 첫 시험에서 USV-02가 누락되어 시스템 문맥에 연결·미연결 목록을 명시한 뒤 재검증했다. 화면의 상태 카드는 모델 문장이 아닌 실제 백엔드 데이터로 표시한다.

현재 세션에 사용 가능한 브라우저 자동화 환경이 없어 브라우저 내 렌더링·클릭 검증은 수행하지 못했다. HTTP 제공·실제 API 연결·이미지 렌더링을 확인했으며 UI의 시각 검수는 남아 있다.

## 실행

README의 시작·종료 명령을 사용한다. 웹 주소는 http://127.0.0.1:8000.
웹에서 카메라 첨부를 선택하면 최신 USV-01 이미지를 모델에 전달한다.
백엔드 대화는 브라우저 탭 메모리에 저장되며 새로고침 시 초기화된다. 학습은 수행하지 않는다.

## 다음 단계

실제 과제·사전 코드 허용 범위를 확인한 뒤 기체 한 대의 이동 제어 → 명령 스키마 검증 → 자연어 명령 실행 → 진행·완료 피드백 순서로 확장한다.
모델이 존재하지 않는 물체나 수치를 주장할 수 있으므로 실제 기체 상태와 수치 계산은 백엔드가 담당해야 한다.
다른 팀원 PC에서 실행 가능한 ROS 이미지 구성과 브라우저 UI 검증도 남아 있다.

종료 과정의 대기 문제를 수정하고 전체 스택의 종료·재시작을 다시 검증했다. 현재 웹·시뮬레이션 서비스는 실행 상태로 유지했다.

## 해상 장면 변경

기본 도형 장면을 평평한 바다 표면, 중심 함정 `escort_ship`, 소형 선체 형태의 `USV-01`로 교체했다. 외부 에셋 다운로드 없이 저장소의 OBJ 메시를 사용한다. 중심 함정은 정적이며 관제 기체 6대 집계에 포함하지 않는다.

이전 도형 테스트 결과는 당시 장면에 대한 기록이다. 현재 카메라에는 함정과 바다가 보이며 ROS 상태·카메라 HTTP 수신을 다시 확인했다.
바다는 평면 시각 표현과 충돌면으로 구성되며, 파도·부력·해류·유체저항은 구현하지 않았다. USV 위치와 카메라만 연동되어 있고 항해 제어는 아직 없다.

## UAV-01 예제 추가

Gazebo 6 기본 `quadcopter.sdf`에서 사용하는 OpenRobotics X3 UAV 버전 4를 다운로드하고 해상 월드에 UAV-01로 추가했다. 원본 모델·저자 정보는 다운로드된 model.config에 유지하고 메시 URI만 로컬 경로로 변경했다.
출처: https://fuel.gazebosim.org/1.0/OpenRobotics/models/X3%20UAV/4

함정 갑판에 지지 충돌면을 추가했다. 실제 Gazebo scene/info에서 UAV-01과 4개 로터 메시를 확인했고, dynamic_pose/info에서 x=15, y=-5, z≈1.505로 갑판에 안정적으로 놓인 것을 확인했다.
예제의 모터 플러그인 4개도 추가했으며 namespace는 UAV-01이다. 이번 작업은 기체 로드·배치 검증이며, 모터 작동·이륙·위치 제어·UAV ROS 상태/카메라·AI 실행 명령은 미검증 또는 미구현이다. 웹의 UAV-01 카드는 아직 미연결로 표시된다.

## 직접 이동 시험

UAV-01에 /UAV-01/gazebo/command/motor_speed (ignition.msgs.Actuators)로 4개 모터 700 rad/s를 전달했고, 갑판 고도 약 1.505m에서 4.496m로 상승한 실제 pose를 확인했다. 이후 660 rad/s만 유지한 상태에서도 관성으로 계속 상승해 약 47.144m에 도달했다. 모터를 0으로 종료했다. 고도 유지·안정적인 호버링을 검증한 것이 아니며 속도/위치 제어기가 필요하다.

USV-01은 /world/navis_prep/set_pose 서비스로 x 좌표를 단계적으로 0→4m 변경했다. ROS→웹 좌표 x=4도 확인했다. 이것은 위치 갱신 시연이며 추진력이나 유체역학 기반 항해 제어는 아니다. VLM은 이 시험에 개입하지 않았다.

## 6대 스폰 및 상태 연결

UAV 총 4대(UAV-01~04), USV 총 2대(USV-01~02)를 구성했다. UAV들은 함정 갑판에 배치하고 USV-02는 (0,5)에 추가했다. 각 기체의 odometry를 독립 ROS 토픽 `/navis/UAV_01/odometry` 등의 형태로 전달한다. 화면 식별자는 하이픈을 유지하며 ROS 토픽에는 밑줄을 사용한다.

모든 기체의 실제 x/y/z·속도·시뮬레이션 시간이 백엔드에 수신되고 /api/state에서 6대 모두 connected=true임을 확인했다. UAV 고도 약 1.505m, USV 높이 약 0.225m와 개별 배치 좌표도 확인했다. 카메라는 USV-01만 연결되어 있다. 배터리나 자동 임무 실행은 구현하지 않았다.

## 2026-10-10 업로드 전 확인

Python 문법, Bash 문법, Git 공백 검사를 통과했다. check_prep.py의 HTTP·6대 상태·JPEG·인증 거부·입력 검증·모델 API 연결 검사 9개를 통과했다. 이 스크립트는 응답의 의미 정확성을 자동 판정하지 않는다.
연결 기체 질문에는 6대를 모두 나열했다. 해상 카메라 설명에서는 문장을 반복하며 출력 토큰 상한에 도달하는 현상이 관측되어, 이미지 응답 품질은 미해결 사항으로 유지한다. 이동 요청에는 실행 불가로 답했고 executed=false였다.

## 2026-10-10 현재 구성: 반구 호위와 8자 기동

이 절이 현재 구성이다. 앞선 6대·USV 정면 카메라 설명은 이전 검증 기록이다. 메인 함선 1척, USV 10대, 공중 UAV 40대의 실제 Gazebo 모델과 ROS odometry를 웹에 연결한다. 이 PC는 aac-2026-image:x86 / Gazebo 6.18 / ROS Humble을 사용한다. UAV는 로컬 시각 모델이며 이전 X3 모터 예제는 실행하지 않는다.

메인 함선은 시뮬레이션 시간 기준 1.5m/s로 직선 전진한다. USV는 함선 중심의 x=115m/y=75m 타원 경계에서 연속적으로 오프셋을 교대한다. UAV는 반지름 130m, 중심 높이 12m의 반구 표면에 8대씩 다섯 위도 편대로 배치된다. 위도 12/26/40/54/68도, longitude ±0.12rad / latitude ±0.04rad 범위에서 38초 주기의 작은 8자 기동을 수행한다. 각 위도 편대는 번갈아 반대 방향으로 천천히 회전한다. 모두 공중 기체이고 갑판 드론은 없다.

경로 조사와 적용:

- [ModalAI Figure Eight](https://docs.modalai.com/voxl-figure-8/)는 VOXL SDK의 실제 자율 경로 추종 예제를 설명하고 [소스 코드](https://gitlab.com/voxl-public/voxl-sdk/services/voxl-vision-hub/-/blob/master/src/offboard_figure_eight.c)를 제공한다. 수학적 Bernoulli lemniscate의 위치·접선 개념을 독립 구현했고, 이를 longitude/latitude에 매핑해 반구를 유지한다. 원본 작은 실내 경로의 크기·좌표를 그대로 복사한 것이 아니다.
- [PX4 개발 키트 튜토리얼](https://px4.io/first-flight-tutorial-for-the-voxl-2-based-px4-autonomy-developer-kit/)은 멀티콥터의 Offboard Figure Eight 모드를 안내한다.
- [PX4 Fixed-Wing Hold](https://docs.px4.io/main/en/flight_modes_fw/hold)에도 Figure 8 Loiter가 있지만 실험적 고정익 기능이며 펌웨어 설정이 필요하다. 이것을 현재 쿼드콥터 모델의 내장 비행 제어라고 주장하지 않는다.
- [ArduPilot Rover Follow](https://ardupilot.org/rover/docs/follow-mode.html)는 선행 차량의 위치와 heading-relative offset을 사용하는 실제 Follow 모드를 설명한다. 본 시연은 이 상대 오프셋 개념을 참고하며 ArduPilot 제어기를 실행하지 않는다.
- [2019 ASV 실험 논문](https://doi.org/10.1016/j.ifacol.2019.12.421)은 4대 수상 기체의 leader-follower 대형 실험을 보고한다. 본 프로젝트에서 동일한 제어 성능을 검증했다는 의미는 아니다.

배 사라짐 수정: 높이를 변형한 바다 메시와 스케일 때문에 수면이 선체를 가렸다. 원본 waterlow.dae의 모든 vertex z=0임을 확인하고 선체보다 낮은 z=-0.25m에서 사용한다. 법선 텍스처만으로 수면을 표현하며 바다 중심도 함선과 함께 갱신한다. VRX 에셋 출처와 Apache-2.0 라이선스는 models/navis_ocean에 보존한다. 파도·부력 물리는 없다.

카메라 offset=(-85,-110,145)m이고 모든 기체의 보수적인 bounding corners가 3% 화면 여백 안에 들어오도록 계산했다. Gazebo GUI도 SHIP-01을 follow하도록 open_gazebo.sh를 갱신했다. 웹에는 반구 가이드와 실제 ROS 위치 마커를 표시한다. GUI 시점과 웹 카메라는 별도다. 브라우저·GUI 직접 클릭 검수는 수행하지 못했다.

검증: 152초 시뮬레이션 경로를 0.1초 간격으로 검사해 40대 모두 반구 표면에 유지되고 최소 드론 간격 8.54m를 확인했다. 기체의 프레임 내 범위는 순찰 구간 및 1000/5000/20000초 시점에서도 검사했다. 수면 높이와 8자 교차 접선·위치 연속성 검사도 통과했다. 실제 실행 중 51대 상태·JPEG·인증 거부·입력 검증 검사 6개를 통과했다. Ollama 연결이 없어 모델 응답 검사는 생략했다.

기동은 Gazebo set_pose_vector 기반 시연이며 실제 동역학, 위협 판단, 충돌 회피 제어기가 아니다. 표시 속도는 정적 모델의 twist=0 대신 실제 odometry 위치·시뮬레이션 시간 변화에서 추정한다(speed_source=odometry_position_delta).

실제 Gazebo 카메라 녹화 검증: 38.7초 시뮬레이션 시간(8자 한 주기 이상) 동안 51대 연결을 확인하고, 함선 갑판의 앞뒤 지점과 USV 10대의 실제 화면 픽셀을 420회 검사했다. 전 검사에서 선체가 수면에 가려지지 않았다. 녹화와 원시 상태는 outputs/hemisphere_patrol.gif / hemisphere_patrol_check.json에 저장한다(Git 제외). UI의 UAV-01 가이드는 이동하는 대형 슬롯 기준의 로컬 8자 경로를 보여준다.

### 실제 선박 형상 에셋 (2026-10-10)

메인 함선은 NPS SAVAGE의 LT Patrick Sullivan 제작 Arleigh Burke high-detail X3D를 가져왔다. 원본 transforms와 재질을 보존하고 Y-up을 Z-up으로 변환했다. Gazebo 재질 덮어쓰기와 법선 누락으로 흰 실루엣이 되던 문제는 59개 원본 표면을 별도 OBJ로 내보내고 표면 법선 및 SDF diffuse/PBR 재질을 명시하여 해결했다. 원본 길이 약 153.8m를 유지한다. 실측 디지털 트윈이나 최신 개장 형상은 아니다.

USV 10척은 Apache-2.0 VRX WAM-V 16ft 원본 형상과 4종 PBR 맵을 사용한다. COLLADA 단위와 export transform을 동일 크기의 미터 단위로 정규화했다. 원본 라이선스와 출처는 각 모델 디렉터리의 LICENSE / ATTRIBUTION.md에 있다.

메인 함선 크기에 맞춰 USV 타원 반경 115/75m, 드론 반구 반경 130m로 확장하고 전체 카메라를 넓혔다. 편대 수와 이동 패턴은 유지하며 지도는 설정 반경에 따라 자동 축척을 사용한다.

### 해상 렌더링 개선

VRX WaveVisual/Wavefield를 Fortress로 포팅했다. visual plugin은 센서 렌더링 및 Gazebo GuiRunner 양쪽에서 사용한다. 셰이더 경로의 모델 파일 기준 해석 차이와 렌더링 entity user-data int 타입을 맞췄고, 누락된 셰이더 파라미터는 null guard로 처리한다. 2.4km 그리드, CWR 3성분, 평균 진폭 .055m/스케일 1.4, 5.5초 주기, 법선 맵·큐브맵 Fresnel 반사를 사용한다. 평평한 원본 수면은 더 아래에 남겨 원거리 수면을 채운다. 선미 뒤 낮은 밀도의 반투명 거품 메시도 추가했다. 시각 표현이며 수치 유체·부력 연동은 아니다.

웹 카메라 view API는 wide/detail 중 사전 정의한 시점만 허용한다. wide/detail 센서는 SHIP-01 링크에 고정된 상공 관측 센서다. telemetry_node가 최대 .5초 간격으로 선택을 읽어 해당 센서 영상을 전달하고, 상태 API는 선택한 시점의 투영 파라미터를 가이드에 전달한다. 카메라를 별도 객체로 이동시키지 않으므로 함선과의 각도·높이·거리가 일정하다. convoy_motion은 /world/navis_prep/clock을 사용하며 뒤늦게 들어온 과거 시각은 무시한다. 시점 전환은 기체 움직임에 영향을 주지 않는다.

검증: 4개 편대/카메라 경계 회귀 검사와 7개 실행 중 API 검사가 통과했다. 두 시점에서 총 16개 실제 JPEG 프레임을 기록했고 매 프레임 51대 연결이 유지됐다. 영상의 함선 픽셀 면적은 전체 약 4,825px에서 근접 약 17,308px로 증가했다. 수면 영역의 시간별 영상 변화도 확인했다. 실행 기록과 GIF는 로컬 outputs/maritime_visual_check.json 및 maritime_live.gif에 저장된다.
