# 노트북 (Control Hub) — 기능 명세

> 📂 [루트](../../README.md) → [공통 docs](../../docs/README.md) → [laptop](../README.md) → **laptop/docs (여기, 가장 상세)**

> **역할: "어떻게 할지" 번역.** AI 서버의 DSL을 실제 모터 명령으로 변환하고, 실시간 안전을 독립적으로 보장한다.
> 위로는 [gRPC](../../docs/3_grpc_interface.md)로 AI 서버와, 아래로는 [Serial](../../docs/4_serial_protocol.md)로 Arduino와 통신한다.

### 세부 문서

| 문서 | 내용 |
|------|------|
| [1_web_app.md](1_web_app.md) | Django 웹앱 4페이지 + 엔드포인트 기능 명세 |
| [2_object_detection_model.md](2_object_detection_model.md) | 객체 탐지 모델 선정 (YOLO-World, 오픈 보캐뷸러리) |
| [3_coordinate_3d_pipeline.md](3_coordinate_3d_pipeline.md) | ChArUco 스테레오 캘리브레이션 + 삼각측량 3D 파이프라인 |
| [4_measurement_validation.md](4_measurement_validation.md) | **측정 검증** — 마커 3D가 실제 강체 운동학과 일치(불변점·강체거리·축복원) |
| [5_coldstart_procedure.md](5_coldstart_procedure.md) | **콜드스타트 절차** — 비전-운동학 자가보정(축복원·PoE FK·sim-real gap·계층 역할) |
| [6_digital_twin_safety.md](6_digital_twin_safety.md) | **디지털 트윈 안전 + 자가학습** — C-space 충돌지도·충돌예측 신경망·능동학습·AI 검증층 |
| [7_ai_integration.md](7_ai_integration.md) | **AI 서버 연동(3페이지)** — gRPC 클라이언트·자연어/음성 제어·3D 미러·set_joint 실물 실행 |
| [8_arm3d_simulator.md](8_arm3d_simulator.md) | **STL 3D 시뮬레이터 + 실물 연동(4페이지)** — 조립·면결합·관절제어 |
| [9_grasp_pipeline.md](9_grasp_pipeline.md) | **물체 파지 파이프라인** — TCP 정의·축보정·파지DB·6DOF IK·방향별 도달영역(capability map) |
| [10_grasp_ik_method.md](10_grasp_ik_method.md) | **데이터 기반 파지 IK — 방법론 도출 과정과 최종 정식화**(학술) — 비용함수 진화(v1→v4)·경로·capability 정식화 |
| [11_gripper_design.md](11_gripper_design.md) | **그리퍼 정밀 설계** — 평행집게 개폐(prismatic) 시뮬·왜 디테일하게(파지 접촉검증)·J7 제어·리깅 드리프트 제거 |
| [12_grasp_orientation_learning.md](12_grasp_orientation_learning.md) | **파지 방향 문제와 접근 조건부 학습** — 형상·바닥에 따른 수직/수평 결정·접근 타입별 데이터·접근 선택 학습 |
| [13_grasp_learning_mlp.md](13_grasp_learning_mlp.md) | **파지 학습 MLP** — 참고 토대·입력 데이터·학습 원리·결과값(분류 92.7%·접근선택 86.8%)·용도·손목(J6)roll 최적화·**참고문헌**(6-DOF 파지 생성) |
| [14_setup_procedure.md](14_setup_procedure.md) | 환경 구성 / 실행 절차 |
| [15_aruco_markers.md](15_aruco_markers.md) | ArUco / ChArUco 마커 명세 |

> **현황:** ① YOLO-World 탐지 + 객체 id, ② ChArUco 스테레오 캘리브레이션(~0.5px, 588mm) + 삼각측량 3D(30mm를 0.32mm 오차로 복원) — 실측 검증. ③ STL 3D 시뮬레이터로 6관절 조립·리깅 완료 → 관절 슬라이더가 3D+실물 서보 동시 구동(연동 ON/OFF). ④ 디지털 트윈 안전검증(C-space 충돌지도·신경망 99.5%·능동학습)·콜드스타트 자가보정. ⑤ **파지 파이프라인**(FK 샘플링 파지 DB 10만·6DOF IK·capability map) + **그리퍼 정밀 개폐**(평행집게 슬라이드·J7 제어). **다음: 손가락-물체 접촉 검증 → AI 서버 연동.**

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
수식 세부는 [2_system_spec.md §3](../../docs/2_system_spec.md) 참조.

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
(4) **STL 3D 시뮬레이터 + 실물 연동**(조립·면결합·관절 슬라이더→3D+실물). 상세는 [1_web_app.md](1_web_app.md), [8_arm3d_simulator.md](8_arm3d_simulator.md).

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
