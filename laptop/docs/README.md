# 노트북 (Control Hub) — 기능 명세

> 📂 [루트](../../README.md) → [공통 docs](../../docs/README.md) → [laptop](../README.md) → **laptop/docs (여기, 가장 상세)**

> **역할: "어떻게 할지" 번역.** AI 서버의 DSL을 실제 모터 명령으로 변환하고, 실시간 안전을 독립적으로 보장한다.
> 위로는 [gRPC](../../docs/grpc_interface.md)로 AI 서버와, 아래로는 [Serial](../../docs/serial_protocol.md)로 Arduino와 통신한다.

### 세부 문서

| 문서 | 내용 |
|------|------|
| [web_app.md](web_app.md) | Django 웹앱 4페이지 + 엔드포인트 기능 명세 |
| [object_detection_model.md](object_detection_model.md) | 객체 탐지 모델 선정 (YOLO-World, 오픈 보캐뷸러리) |
| [coordinate_3d_pipeline.md](coordinate_3d_pipeline.md) | ChArUco 스테레오 캘리브레이션 + 삼각측량 3D 파이프라인 |
| [measurement_validation.md](measurement_validation.md) | **측정 검증** — 마커 3D가 실제 강체 운동학과 일치(불변점·강체거리·축복원) |
| [coldstart_procedure.md](coldstart_procedure.md) | **콜드스타트 절차** — 비전-운동학 자가보정(축복원·PoE FK·sim-real gap·계층 역할) |
| [digital_twin_safety.md](digital_twin_safety.md) | **디지털 트윈 안전 + 자가학습** — C-space 충돌지도·충돌예측 신경망·능동학습·AI 검증층 |
| [arm3d_simulator.md](arm3d_simulator.md) | **STL 3D 시뮬레이터 + 실물 연동(4페이지)** — 조립·면결합·관절제어 |
| [setup_procedure.md](setup_procedure.md) | 환경 구성 / 실행 절차 |
| [aruco_markers.md](aruco_markers.md) | ArUco / ChArUco 마커 명세 |

> **현황:** ① YOLO-World 탐지 + 객체 id, ② ChArUco 스테레오 캘리브레이션(~0.5px, 588mm) + 삼각측량 3D(30mm를 0.32mm 오차로 복원) — 실측 검증. ③ **STL 3D 시뮬레이터로 6관절 조립·리깅 완료 → 관절 슬라이더가 3D+실물 서보 동시 구동(연동 ON/OFF). AI 연동 직전 단계.**

---

## 1. 하드웨어 / 환경

| 항목 | 값 |
|------|-----|
| CPU | Intel i7-12700H |
| GPU | RTX 3050 (4GB VRAM) |
| RAM | 16GB DDR4 |
| 언어 | Python 3.12 |
| 웹/제어 계층 | Django (project=`config`, app=`armvision`) |
| 역할 | 제어 + 비전 처리 |

---

## 2. 기능 책임

| 영역 | 책임 |
|------|------|
| 비전 | YOLO-World 객체 탐지(실시간, GPU), 삼각측량, ChArUco/ArUco 인식, 좌표 변환 |
| 운동학 | Pieper IK, 순기구학, S-curve 보간, 특이점 회피, PWM 매핑 |
| DSL | AI 서버 DSL 4단계 검증 + op 핸들러 실행 |
| 안전 | 카메라 기반 4계층 비상 정지 (AI 서버 비의존) |
| 그립 | PCA 기반 그립 자세 결정, ToF 폐루프 정밀 하강 |
| 캘리브레이션 | 콜드스타트 visual-kinematic, DH LM 최적화 |
| 통신 | gRPC 클라이언트(AI 서버), Serial 브릿지(Arduino) |

---

## 3. 4단계 변환 사슬 (핵심)

```
DSL + 픽셀좌표 → ①삼각측량 → ②좌표변환 → ③IK(Pieper) → ④S-curve+PWM → Arduino(50Hz)
```
수식 세부는 [system_spec.md §3](../../docs/system_spec.md) 참조.

---

## 4. 안전 (독립 보장)

- **메커니즘 A (ToF 폐루프):** 그립 정밀 제어 전용, 비상 정지 아님.
- **메커니즘 B (카메라 4계층):** 사람 침입 / 객체 급격 이동 / 경로 장애물 / 타겟 소실.
- 비상 정지는 AI 서버 응답에 의존하지 않으며, 응답 예산 <100ms.
- AI 서버 heartbeat 3초 무응답 시 독립적으로 비상 정지.

---

## 5. 코드 구조 (현행 — Django 웹앱)

노트북 계층은 **Django 웹앱**으로 구현되어 있다. 4개 페이지를 제공한다:
(1) 카메라·객체탐지(좌/우 카메라 선택), (2) 캘리브레이션 위저드(6단계), (3) 자연어 제어(골격),
(4) **STL 3D 시뮬레이터 + 실물 연동**(조립·면결합·관절 슬라이더→3D+실물). 상세는 [web_app.md](web_app.md), [arm3d_simulator.md](arm3d_simulator.md).

```
laptop/
├── manage.py
├── config/                  # Django 프로젝트
├── armvision/               # 메인 앱
│   ├── camera.py            # 카메라 캡처(자가치유) + 좌/우 선택(cam_config.json)
│   ├── detector.py          # YOLO-World 객체 탐지
│   ├── charuco.py           # ChArUco 캘리브레이션
│   ├── stereo3d.py          # 스테레오 삼각측량 3D
│   ├── arduino_bridge.py    # 실물 로봇팔 시리얼(pyserial, COM9)
│   ├── views.py
│   └── templates/           # arm3d.html = 3D 시뮬레이터(조립/결합/제어)
├── cad/                     # 팀원 STL 부품 + assembly.json(조립 저장)
├── calibration/
│   ├── calibrate_stereo.py
│   ├── validate_triangulation.py
│   ├── make_targets.py
│   └── make_arm_markers.py
└── docs/
```

> **참고(예정):** 실시간 제어 루프(camera/safety/arduino/command 병행 실행)는 향후 asyncio 기반으로 구현 예정이다. 현재 웹/제어 계층은 Django다.

---

## 6. 주요 의존성 (예정)

`django`, `ultralytics`(YOLO-World `yolov8m-worldv2`), `grpcio`, `pyserial`, `opencv-python`, `opencv-contrib-python`(ChArUco/ArUco), `numpy`, `scipy`, `torch`, `torchvision`.

---

## 7. 단독 검증 항목 (현 보유 하드웨어로 가능)

- [x] 카메라 2대 캡처 + YOLO-World 실시간 객체 탐지 구동 확인 (GPU, RTX 3050)
- [x] ChArUco 스테레오 캘리브레이션 (재투영오차 ~0.5px, 베이스라인 588mm)
- [x] 삼각측량 정확도 검증 (보드 30mm를 0.32mm 오차로 복원)
- [x] STL 3D 시뮬레이터로 6관절 조립·리깅 + 관절 슬라이더 구동
- [x] Arduino Serial 펄스 전송(`arduino_bridge.py` → `u ch us`) + 4페이지 연동 토글
- [ ] IK/FK 순수 Python 단위 테스트 (로봇 없이)
- [ ] (ToF 센서 입고 후) VL53L0X 측정 + 이진 패킷 프로토콜
