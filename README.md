# 🦾 AI 기반 6-DOF 음성 제어 로봇팔

> **Voice-Controlled Autonomous Grasping Manipulator**
> 대진대학교 캡스톤 디자인 — 한국어 음성 명령으로 객체를 인식하고 안전하게 그립하는 분산 AI 추론 기반 6-DOF 로봇팔.

```
사용자: "빨간 컵을 책 옆에 놔줘"
   ↓
음성 인식 → 객체 인식 → 의도 파악 → 동작 계획 →
IK 계산 → 안전 검증 → 모터 제어 → 그립 → 이동 → 놓기
```

---

## 시스템 구조

3계층 분산 아키텍처. 의미 추론은 위로, 결정적·실시간 작업은 아래로.

| 계층 | 장치 | 역할 | 주요 기술 |
|------|------|------|----------|
| **Layer 3** | MSI EdgeXpert | "무엇을 할지" 결정 | Whisper · Gemma 4 · Qwen3 · FAISS |
| **Layer 2** | 노트북 | "어떻게 할지" 번역 | RF-DETR · OpenCV · Pieper IK · 안전 감시 |
| **Layer 1** | Arduino Mega 2560 | "실제 실행" | PCA9685 · VL53L0X ToF |

```
AI 서버  ──gRPC/Protobuf──  노트북  ──USB Serial(CRC-16)──  Arduino
```

---

## 정량 목표

| 항목 | 목표 |  | 항목 | 목표 |
|------|------|--|------|------|
| 그립 정밀도 | ±2mm | | 비상 정지 응답 | <100ms |
| 명령→그립 완료 | <10초 | | 페이로드 | 150g |
| 객체 인식 정확도 | ≥95% | | 자유도 / 제어주기 | 6-DOF / 50Hz |

---

## 저장소 구조

```
daejin_capstone_design_ai_robot_arm/
├── docs/          # 공통 명세 (아키텍처·gRPC·Serial·DSL·규약)
├── ai_server/     # EdgeXpert AI 추론 서버 (Python)
│   └── docs/
├── laptop/        # 제어 허브 (Python)
│   └── docs/
└── arduino/       # 펌웨어 (PlatformIO / C++)
    └── docs/
```

각 컴포넌트 폴더의 `docs/`에는 해당 계층의 **기능 명세**를, 루트 `docs/`에는 여러 계층이 **공통으로 합의해야 하는 명세**를 둔다.

---

## 문서

| 문서 | 내용 |
|------|------|
| [docs/system_spec.md](docs/system_spec.md) | 시스템 마스터 사양 (전체 레퍼런스) |
| [docs/architecture.md](docs/architecture.md) | 3계층 구조·책임 분리 |
| [docs/grpc_interface.md](docs/grpc_interface.md) | AI 서버 ↔ 노트북 인터페이스 |
| [docs/serial_protocol.md](docs/serial_protocol.md) | 노트북 ↔ Arduino 인터페이스 |
| [docs/dsl_spec.md](docs/dsl_spec.md) | JSON DSL 명령 언어 |
| [docs/conventions.md](docs/conventions.md) | 좌표계·단위·명명 규약 |
| [ai_server/docs](ai_server/docs/README.md) · [laptop/docs](laptop/docs/README.md) · [arduino/docs](arduino/docs/README.md) | 컴포넌트별 기능 명세 |

---

## 학술적 차별화

1. **Code-as-Policies** — LLM이 제한된 DSL을 직접 생성 (RT-2 / ProgPrompt 계열)
2. **Visual-Kinematic Self-Calibration** — 로봇이 자기 자신을 측정해 운동학 보정 (±15mm → ±2mm)
3. **RAG-Grounded** — FAISS + Qwen3 임베딩으로 LLM 환각 차단
4. **카메라 기반 Defense-in-Depth Safety** — 4계층 독립 검증

---

## 현재 상태

📌 **문서/명세 정비 단계.** 부품은 ToF 센서·전선을 제외하고 확보. 로봇팔 조립 전이며, 실시간 객체 인식 및 EdgeXpert 모델 구동 검증 예정.

---

> 대진대학교 캡스톤 디자인 프로젝트
