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
| **Layer 2** | 노트북 | "어떻게 할지" 번역 | Django · YOLO-World · OpenCV · Pieper IK · 안전 감시 |
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

## 🛠️ 기술 스택

### 💻 핵심 개발 및 AI/ML 스택

| 카테고리 | 기술 스택 |
|----------|-----------|
| **사용 언어** | ![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![C++](https://img.shields.io/badge/C%2B%2B-00599C?style=flat&logo=cplusplus&logoColor=white) |
| **음성 인식 (STT)** | ![Whisper](https://img.shields.io/badge/Whisper_Large--v3-412991?style=flat&logo=openai&logoColor=white) |
| **LLM / VLM** | ![Gemma](https://img.shields.io/badge/Gemma_4-4285F4?style=flat&logo=google&logoColor=white) |
| **객체 탐지** | ![YOLO-World](https://img.shields.io/badge/YOLO--World-6E56CF?style=flat) |
| **벡터 데이터베이스** | ![FAISS](https://img.shields.io/badge/FAISS-009688?style=flat&logo=meta&logoColor=white) |
| **임베딩 모델** | ![Qwen3-Embedding](https://img.shields.io/badge/Qwen3--Embedding--8B-615CED?style=flat) |
| **학습 / 추론 프레임워크** | ![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat&logo=pytorch&logoColor=white) ![Transformers](https://img.shields.io/badge/Transformers-FFD21E?style=flat&logo=huggingface&logoColor=black) |
| **비전 / 수치 연산** | ![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat&logo=opencv&logoColor=white) ![NumPy](https://img.shields.io/badge/NumPy-013243?style=flat&logo=numpy&logoColor=white) ![SciPy](https://img.shields.io/badge/SciPy-8CAAE6?style=flat&logo=scipy&logoColor=white) |

### 🤖 제어 · 통신 · 하드웨어

| 카테고리 | 기술 스택 |
|----------|-----------|
| **노트북 웹/제어 계층** | ![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white) |
| **MCU / 펌웨어** | ![Arduino](https://img.shields.io/badge/Arduino_Mega_2560-00878F?style=flat&logo=arduino&logoColor=white) ![PlatformIO](https://img.shields.io/badge/PlatformIO-FF7F00?style=flat&logo=platformio&logoColor=white) |
| **모터 제어** | ![PCA9685](https://img.shields.io/badge/PCA9685-027BC4?style=flat) |
| **센서** | ![VL53L0X](https://img.shields.io/badge/VL53L0X_ToF-03234B?style=flat&logo=stmicroelectronics&logoColor=white) |
| **통신** | ![gRPC](https://img.shields.io/badge/gRPC-244B5A?style=flat) ![Protobuf](https://img.shields.io/badge/Protobuf-244B5A?style=flat) ![USB Serial](https://img.shields.io/badge/USB_Serial-5A5A5A?style=flat) ![I2C](https://img.shields.io/badge/I2C-5A5A5A?style=flat) |
| **비동기 제어 (예정: 실시간 제어 루프)** | ![asyncio](https://img.shields.io/badge/asyncio-3776AB?style=flat&logo=python&logoColor=white) |
| **AI 서버 / GPU** | ![EdgeXpert](https://img.shields.io/badge/MSI_EdgeXpert_(GB10)-CC0000?style=flat&logo=msi&logoColor=white) ![RTX 3050](https://img.shields.io/badge/RTX_3050-76B900?style=flat&logo=nvidia&logoColor=white) |

### 🤝 협업 및 기타

| 카테고리 | 기술 스택 |
|----------|-----------|
| **형상 관리 / 협업** | ![Git](https://img.shields.io/badge/Git-F05032?style=flat&logo=git&logoColor=white) ![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white) ![Notion](https://img.shields.io/badge/Notion-000000?style=flat&logo=notion&logoColor=white) ![Google Drive](https://img.shields.io/badge/Google_Drive-4285F4?style=flat&logo=googledrive&logoColor=white) |
| **테스트** | ![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=flat&logo=pytest&logoColor=white) |
| **개발 환경** | ![VS Code](https://img.shields.io/badge/VS_Code-007ACC?style=flat&logo=visualstudiocode&logoColor=white) |

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

📌 **하드웨어 조립 완료 · 노트북 비전 파이프라인 구동 단계.**
- 6-DOF 로봇팔 **조립 완료**.
- Arduino + PCA9685로 J1~J6 서보 **펄스 캘리브레이션 완료** (관절별 0°/180° 실측, [arduino/docs/servo_calibration.md](arduino/docs/servo_calibration.md)).
- 노트북 **Django 비전 파이프라인 구동 중**: YOLO-World 객체 탐지 + ChArUco 스테레오 캘리브레이션(재투영오차 ~0.5px, 베이스라인 588mm) + 삼각측량 3D 좌표(보드 30mm를 0.32mm 오차로 복원).
- **4페이지 웹 UI**(Django): 카메라·탐지 / 캘리브레이션 위저드 / 자연어 제어(골격) / 3D 로봇팔 뷰어(Three.js). → [laptop/docs/web_app.md](laptop/docs/web_app.md)
- **미통합:** ToF(VL53L0X) 센서. **이후 단계:** EdgeXpert / AI 서버 연동, ArduinoBridge(실물 구동) 연결.

---

> 대진대학교 캡스톤 디자인 프로젝트
