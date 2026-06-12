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

**바깥은 개요, 안으로 갈수록 상세** — 폴더로 들어갈수록 구체적인 문서가 나온다.

```
daejin_capstone_design_ai_robot_arm/
├── README.md        # ← 지금 이 문서: 목적·기술스택·기능·현황 (쇼케이스)
├── docs/            # 공통: 아키텍처 + 왜 이렇게 나눴는지 + 인터페이스 명세
├── ai_server/       # L3 AI 추론 서버   README + docs/  (무엇을 할지)
├── laptop/          # L2 제어 허브       README + docs/  (어떻게 할지)
└── arduino/         # L1 펌웨어          README + docs/  (실제 실행)
```

- 각 컴포넌트 **폴더 루트 `README.md`** = 그 폴더의 개요(역할·하위 폴더 지도).
- 각 컴포넌트 **`docs/`** = 기능 명세(가장 상세).
- 루트 **`docs/`** = 계층이 공통으로 합의하는 명세.

---

## 문서 안내

| 더 알고 싶다면 | 문서 |
|----------------|------|
| **전체 아키텍처 · 왜 3계층인지** | [docs/README.md](docs/README.md) · [docs/architecture.md](docs/architecture.md) |
| 계층 간 인터페이스 | [grpc_interface](docs/grpc_interface.md) · [serial_protocol](docs/serial_protocol.md) · [dsl_spec](docs/dsl_spec.md) · [conventions](docs/conventions.md) · [system_spec](docs/system_spec.md) |
| **노트북 — 비전·3D 시뮬·실물 연동** | [laptop/README.md](laptop/README.md) → [laptop/docs](laptop/docs/README.md) |
| **3D 모델링·조립·연동** (방법 포함) | [laptop/docs/arm3d_simulator.md](laptop/docs/arm3d_simulator.md) |
| **ChArUco 캘리브레이션** (방법 포함) | [laptop/docs/coordinate_3d_pipeline.md](laptop/docs/coordinate_3d_pipeline.md) |
| 펌웨어 · 서보 캘리브레이션 | [arduino/README.md](arduino/README.md) → [arduino/docs](arduino/docs/README.md) |
| AI 서버 (예정) | [ai_server/README.md](ai_server/README.md) |

---

## 학술적 차별화

1. **Code-as-Policies** — LLM이 제한된 DSL을 직접 생성 (RT-2 / ProgPrompt 계열)
2. **Visual-Kinematic Self-Calibration** — 로봇이 자기 자신을 측정해 운동학 보정 (±15mm → ±2mm)
3. **RAG-Grounded** — FAISS + Qwen3 임베딩으로 LLM 환각 차단
4. **카메라 기반 Defense-in-Depth Safety** — 4계층 독립 검증

---

## 현재 상태

📌 **하드웨어 조립 완료 · 비전·시뮬레이션·실물 연동까지 구동 — AI 연동 직전 단계.**

- 6-DOF 로봇팔 **조립 완료**. Arduino + PCA9685로 J1~J6 서보 **펄스 캘리브레이션 완료** (관절별 0°/180° 실측, [arduino/docs/servo_calibration.md](arduino/docs/servo_calibration.md)).
- **비전 (실측 검증):** YOLO-World 객체 탐지(GPU) + **ChArUco 스테레오 캘리브레이션**(`DICT_5X5_100`, 6×8, 30/23mm, 재투영오차 ~0.5px, 베이스라인 588mm) + 삼각측량 3D 좌표(보드 30mm를 0.32mm 오차로 복원). → [laptop/docs/coordinate_3d_pipeline.md](laptop/docs/coordinate_3d_pipeline.md)
- **STL 3D 시뮬레이터 + 실물 연동 (4페이지, Three.js):** 팀원 STL 부품을 브라우저에서 **면대면 결합(CATIA식 원통 동심 + 평면 일치)** 으로 직접 조립 → **6관절 리깅 완료**. 관절 슬라이더가 3D를 돌리고, **연동 ON 시 실제 서보를 동시 구동**(각도→펄스 변환은 노트북, 아두이노엔 `u ch us` 전송 — 펌웨어 수정 불필요). → [laptop/docs/arm3d_simulator.md](laptop/docs/arm3d_simulator.md)
- **웹 UI 4페이지**(Django): 카메라·탐지(좌/우 카메라 선택) / 캘리브레이션 위저드 / 자연어 제어(골격) / **STL 3D 시뮬레이터·실물 연동**. → [laptop/docs/web_app.md](laptop/docs/web_app.md)
- **이후 단계:** 베이스 ArUco로 카메라→로봇 좌표변환(T), EdgeXpert / AI 서버(Whisper·Gemma) 연동 → 자연어 명령이 위 연동 경로로 로봇 구동. **미통합:** ToF(VL53L0X), 이진 시리얼 프로토콜.

---

> 대진대학교 캡스톤 디자인 프로젝트
