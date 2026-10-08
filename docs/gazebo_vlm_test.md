# Gazebo + MiniCPM-V 동시 실행 확인

확인일: 2026-10-09 한국시간.

## 실행 조건

- 호스트 Gazebo Sim 8.15.0, GUI + server 동시 실행
- 설치된 기본 `camera_sensor.sdf` 월드 사용 (UAV·USV 시나리오 아님)
- 기본 실행은 Intel 내장 GPU 렌더링으로 확인되어 테스트용 인스턴스를 종료하고 NVIDIA PRIME offload로 재실행
- Ogre 로그: NVIDIA GeForce RTX 5080 Laptop GPU 렌더링 확인
- MiniCPM-V 4.5 Q4_K_M, context 4096, think=false, temperature=0, 최대 출력 256토큰
- 입력은 GUI 전체 스크린샷이 아니라 실제 Gazebo /camera 토픽의 320×240 RGB 센서 영상
- GZ_PARTITION=d4d-vlm-check로 기존 시뮬레이션과 분리

## 실측

| 회차 | 첫 답변 토큰 | 전체 응답 | 추론 중 수신한 카메라 프레임 | 종료 시 실시간 배율 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 0.22초 | 3.01초 | 91 | 1.019 |
| 2 | 0.07초 | 2.74초 | 83 | 1.001 |
| 3 | 0.07초 | 2.78초 | 84 | 1.000 |

- 전체 NVIDIA GPU 메모리 샘플 최대: 7085 MiB (Ollama와 Gazebo 및 기존 데스크톱 프로세스 포함)
- 두 프로세스가 함께 실행되고, 추론 중 시뮬레이션 시간이 계속 증가하는 것 확인
- 2·3회는 거의 동일한 정적 이미지와 질문을 반복했고 입력 토큰 125개 중 124개가 캐시됨. 새로운 복잡한 영상의 지연을 대표하지 않음
- 모델은 앞선 테스트에서 이미 로드·초기 준비된 상태. 최초 로딩 시간 미포함

## 이미지 해석 품질

검사한 NVIDIA 캡처에는 왼쪽 빨간 상자와 오른쪽 빨강·흰색 교통콘이 보인다. 모델은 색상과 대략적인 위치를 언급했으나, 이미지에 없는 녹색 원을 추가했다. 상자와 콘의 잘림 여부도 잘못 판단했다. 교통콘을 콘크리트로 표현하고 일부 외국어를 섞었다.
따라서 동시 실행과 센서 이미지 입력은 성공했지만, 해당 장면의 정확한 해석은 통과로 판정하지 않는다. 자유로운 이미지 설명을 실행 명령의 근거로 바로 사용하기에는 신뢰도가 부족하다.
UAV 4대·USV 2대, 실제 해상 장면, 고해상도 카메라, ROS 브릿지·웹 지연은 이번 테스트 대상이 아니다.

## 재현

프로젝트 루트에서 별도 터미널 두 개로 실행한다.

```bash
GZ_PARTITION=d4d-vlm-check QT_QPA_PLATFORM=xcb __NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia __VK_LAYER_NV_optimus=NVIDIA_only gz sim -r /usr/share/gz/gz-sim8/worlds/camera_sensor.sdf
```

```bash
python3 scripts/test_gazebo_vlm.py
```

Pillow와 호스트의 gz.transport13, gz.msgs10 Python 바인딩이 필요하다. 재실행하면 결과 파일을 덮어쓴다.
원본 캡처·응답·GPU 샘플·Gazebo 로그: `outputs/gazebo_vlm/` (Git 제외).
검증 후 테스트용 Gazebo는 종료한다. 기존 프로젝트의 컨테이너나 설정은 변경하지 않았다.
