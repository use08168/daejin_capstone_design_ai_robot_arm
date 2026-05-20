# 노트북 (Control Hub) — 기능 명세

> **역할: "어떻게 할지" 번역.** AI 서버의 DSL을 실제 모터 명령으로 변환하고, 실시간 안전을 독립적으로 보장한다.
> 위로는 [gRPC](../../docs/grpc_interface.md)로 AI 서버와, 아래로는 [Serial](../../docs/serial_protocol.md)로 Arduino와 통신한다.

---

## 1. 하드웨어 / 환경

| 항목 | 값 |
|------|-----|
| CPU | Intel i7-12700H |
| GPU | RTX 3050 (4GB VRAM) |
| RAM | 16GB DDR4 |
| 언어 | Python 3.11 |
| 역할 | 제어 + 비전 처리 |

---

## 2. 기능 책임

| 영역 | 책임 |
|------|------|
| 비전 | RF-DETR 객체 탐지(실시간), 삼각측량, ArUco 인식, 좌표 변환 |
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

## 5. 예정 코드 구조 (구현 단계)

```
laptop/
├── pyproject.toml
├── src/
│   ├── main.py
│   ├── controllers/        # robot_controller, dsl_executor, safety_monitor
│   ├── kinematics/         # dh_params, FK, IK(Pieper), trajectory, singularity
│   ├── vision/             # camera_capture, rf_detr, triangulation, aruco, transform
│   ├── communication/      # grpc_client, arduino_bridge, packet_codec
│   ├── calibration/        # camera_calib, visual_kinematic, dh_optimizer
│   ├── grasp/              # pca_pose, reactive_descent, gripper_width
│   └── dsl/                # ops, validator, executor
└── tests/
```

메인 컨트롤러는 asyncio 기반으로 camera/safety/arduino/command 루프를 병행 실행.

---

## 6. 주요 의존성 (예정)

`grpcio`, `pyserial`, `opencv-python`, `opencv-contrib-python`(ArUco), `numpy`, `scipy`, `torch`, `torchvision`, `transformers`(RF-DETR).

---

## 7. 단독 검증 항목 (현 보유 하드웨어로 가능)

- [ ] 카메라 2대 캡처 + RF-DETR 실시간 객체 탐지 구동 확인
- [ ] 체스보드 내부 캘리브레이션 스크립트
- [ ] 삼각측량 정확도 검증
- [ ] IK/FK 순수 Python 단위 테스트 (로봇 없이)
- [ ] (ToF 센서·전선 입고 후) Arduino Serial 통신 검증
