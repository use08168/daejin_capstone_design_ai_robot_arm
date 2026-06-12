# 시스템 마스터 사양 — AI 기반 6-DOF 로봇팔

> **Voice-Controlled Autonomous Grasping Manipulator** · 대진대 캡스톤 디자인
> 본 문서는 프로젝트 전체의 마스터 레퍼런스다. 인터페이스 세부는 별도 문서로 분리한다:
> [architecture](architecture.md) · [gRPC](grpc_interface.md) · [Serial](serial_protocol.md) · [DSL](dsl_spec.md) · [conventions](conventions.md)

---

## 0. 한 줄 정의

한국어 음성 명령으로 객체를 인식하고 안전하게 그립하는 분산 AI 추론 기반 6-DOF 로봇팔.

전체 아키텍처·책임 분리·정량 목표는 [architecture.md](architecture.md) 참조.

---

## 1. AI 모델 스택

| 모델 | 역할 | 위치 |
|------|------|------|
| Whisper Large-v3 | 한국어 STT | AI 서버 |
| Gemma 4 (멀티모달) | LLM 추론 + VLM (객체 매칭, 의도 파싱, DSL 생성) | AI 서버 |
| YOLO-World (`yolov8m-worldv2`) | 실시간 객체 탐지 (오픈 보캐뷸러리, Detection only, 마스크 없음) | 노트북 (RTX 3050, CUDA) |
| Qwen3-Embedding-8B | RAG 벡터 임베딩 (dim 8192) | AI 서버 |

비전 처리 분담:
- **노트북 (결정적·실시간):** YOLO-World 탐지([laptop/docs/object_detection_model.md](../laptop/docs/object_detection_model.md)), OpenCV 삼각측량, ChArUco/ArUco, 좌표 변환, 비상 정지 감시.
- **AI 서버 (의미 추론):** 자연어-객체 매칭, 속성 인식, 의도 파싱, JSON DSL 생성.

---

## 2. 명령 처리 흐름

음성 → STT → 객체 매칭 → 의도 파싱 → JSON DSL → 노트북 검증 → IK → 모터 제어.
DSL 카탈로그·스키마·검증은 [dsl_spec.md](dsl_spec.md) 참조.

---

## 3. 수학적 모델링 — 4단계 변환 사슬

노트북은 매 동작마다 다음 4단계를 수행한다.

```
[입력] Gemma DSL + YOLO-World 픽셀 좌표
   ↓ ① 삼각측량 (Triangulation)        →  cv2.triangulatePoints, SVD
[3D 세계 좌표]
   ↓ ② 좌표계 변환 (Frame Transform)   →  동차변환 행렬 T (ArUco)
[로봇 베이스 좌표]
   ↓ ③ 역기구학 (Inverse Kinematics)   →  Pieper 분해
[6 관절각]
   ↓ ④ 보간 + PWM 매핑                 →  S-curve, 50Hz
[출력] Arduino PWM 명령 시퀀스
```

### 3.1 삼각측량
- 핀홀 카메라 모델 `s·[u,v,1]ᵀ = K·[R|t]·[X,Y,Z,1]ᵀ`
- 두 카메라 픽셀로 선형 시스템 구성 → SVD로 해 (`X = V[:,-1]`, 동차좌표 정규화)
- 구현: `cv2.triangulatePoints(P1, P2, pixel1, pixel2)`

### 3.2 좌표계 변환
- 동차변환 `T = [[R, t],[0,1]]`, `X_robot = T·X_world`
- `T`는 ArUco `estimatePoseSingleMarkers`로 산출, RAG에 저장.

### 3.3 역기구학 — Pieper 분해
부분 구형 손목 구조를 이용해 위치 IK(J1~J3)와 자세 IK(J4~J6)를 분리.

| 단계 | 내용 |
|------|------|
| 1 | 손목 중심 `p_wrist = p_target - d₆·R_target[:,2]` |
| 2 | `θ₁ = atan2(yw, xw)` |
| 3 | 평면 환원 `r=√(xw²+yw²)`, `s=zw-d₁` |
| 4 | `θ₃` 코사인 법칙 (`±` → elbow-up/down, `|D|>1`이면 도달 불가) |
| 5 | `θ₂ = atan2(s,r) - atan2(L₃sinθ₃, L₂+L₃cosθ₃)` |
| 6 | 자세 분리 `R₆³ = (R₃⁰)ᵀ·R_target` |
| 7 | YZY 오일러 분해 → θ₄, θ₅, θ₆ |
| 8 | 특이점 회피 (`|sinθ₅| < sin5°` → θ₄ 고정) |
| 9 | 8개 후보 중 최적해 선택 (관절 한계·충돌·워크스페이스 + 가중 비용 `J(θ)=Σwᵢ(θᵢ-θᵢ_cur)²`, 큰 서보일수록 wᵢ 작게) |

DH 파라미터 초기값(설계 도면 기반, 콜드스타트로 실측 갱신):

| 관절 | a(mm) | α(rad) | d(mm) | θ_offset |
|------|-------|--------|-------|----------|
| J1 | 0 | π/2 | 131.56 | 0 |
| J2 | 110.4 | 0 | 0 | -π/2 |
| J3 | 96.0 | 0 | 0 | 0 |
| J4 | 0 | π/2 | 73.18 | 0 |
| J5 | 0 | -π/2 | 66.39 | 0 |
| J6 | 0 | π/2 | 43.6 | 0 |

### 3.4 보간 + PWM 매핑
- S-curve `s(t)=3t²-2t³` (양 끝 속도 0 → 충격 없음), `θ(t)=θ_cur+s(t)·(θ_tgt-θ_cur)`
- 시간 분할 `T = max|Δθ|/60`, `N = T×50`
- PWM 매핑은 [conventions.md](conventions.md) 참조.

---

## 4. 콜드스타트 — Visual-Kinematic 캘리브레이션

3D 프린트 누적 오차(±10~15mm)를 로봇 자가 측정으로 ±2mm까지 보정.

| 단계 | 내용 |
|------|------|
| 1 내부 캘리브레이션 | ChArUco 보드 20~30쌍 → `cv2.calibrateCamera` (K, distortion) |
| 2 외부 캘리브레이션 | 베이스 ArUco → 카메라-로봇 변환 T |
| 3 관절 한계 측정 | 각 관절 ±방향 회전, 물리 한계 감지 |
| 4 자세 격자 순회 | 75~100점, 각 점 IK 이동 후 그리퍼 ArUco 측정 → {θₖ, p_expected, p_measured} |
| 5 DH 최적화 | Levenberg-Marquardt, `C(DH)=Σ‖FK(θₖ,DH)-p_measured‖²`, `scipy.optimize.least_squares(method='lm')` |
| 6 RAG 등록 | Qwen3 임베딩 → FAISS 저장 (메타: 보정일, 평균오차, DH) |

검증: `ε_avg < 5mm` 합격, 아니면 재캘리브레이션.

---

## 5. 그립 자세 결정 — PCA 기반

객체 형상에 따라 그립 전략 차등 (둥근 컵=top-down, 펜=길이방향 수직, 책=옆 가장자리).

- 포인트 집합 공분산 `C`의 고유값 분해 → 주축 v₁, 부축 v₂
- 이심률 `e=√(λ₁/λ₂)`, 주축각 `α=atan2(v₁[1],v₁[0])`
- `e<1.5`→top-down(θ₄=0), `e>2.5 & 폭>20`→side(θ₄=90), 중간→angled(θ₄=45)
- `θ₅ = α_robot - 90°`, 그리퍼 폭 = `minor_width + 10mm`
- **YOLO-World는 마스크가 없으므로** bbox 종횡비 근사 + Gemma VLM 질의로 대체.

---

## 6. 안전 메커니즘 — 이중 구조

### 6.1 메커니즘 A — ToF 폐루프 (그립 정밀 제어 전용, 비상 정지 아님)
```
v_descent = Kp·(d_measured - d_target)·min(1, d_measured/100),  Kp=0.05, d_target=5mm
그립 트리거: d < 10mm
```
3단계: open-loop 빠른 접근 → ToF 폐루프 하강 → 그립.

### 6.2 메커니즘 B — 카메라 기반 비상 정지 (4계층 Defense-in-Depth)

| 계층 | 감지 |
|------|------|
| 1 | 사람 침입 (person bbox ∩ workspace) |
| 2 | 객체 급격 이동 (>500 mm/s) |
| 3 | 경로상 장애물 (waypoint-obstacle <30mm) |
| 4 | 타겟 시야 사라짐 (최근 3프레임 부재) |

비상 정지 동작: 관절 동결 → 그리퍼 상태 유지 → 명령 잠금 → AI 서버 알림 → 사용자 확인 → 홈 복귀.

응답 시간 예산: YOLO-World ~20ms + 검증 <5ms + 송신 <1ms + 서보 정지 <5ms = **<100ms**.

> ToF는 비상 정지에 사용하지 않는다. 비상 정지는 카메라 기반이며 AI 서버 응답에 의존하지 않는다.

---

## 7. RAG 지식 베이스 스키마 (요약)

```yaml
rag_db:
  dh_parameters:    { J1:[a,α,d,θ_off], ... }
  joint_limits:     { J1:[min,max], ... }
  workspace:        { x_range, y_range, z_range }
  camera_calibration: { cam1:{K,R,t,dist}, cam2:{...} }
  object_database:  { red_cup:{weight_g, dims_mm}, book:{...}, pen:{...} }
  metadata:         { calibration_date, avg_error_mm }
```

---

## 8. 학술적 차별화 포인트

1. **Code-as-Policies** — LLM이 제한된 DSL을 직접 생성 (RT-2, ProgPrompt 계열)
2. **Visual-Kinematic Self-Calibration** — 로봇 자가 측정 운동학 보정
3. **RAG-Grounded** — FAISS+Qwen3로 LLM 환각 차단, 모든 수치를 검증된 사실로 grounding
4. **카메라 기반 Defense-in-Depth Safety** — 4계층 독립 검증

핵심 참고: Zhang(2000) 카메라 캘리브레이션, Hartley&Zisserman(2003) 삼각측량, Denavit-Hartenberg(1955), Pieper(1968) IK, Marquardt(1963) LM, Liang et al.(2022) Code-as-Policies.

---

## 9. 위험 요소 (요약)

| 위험 | 대응 |
|------|------|
| YOLO-World GPU 부족 | Detection-only, batch=1 |
| 3D 프린트 강도 | 카운터웨이트 2kg, 페이로드 제한 150g |
| J3 토크 부족 | DS3235 업그레이드 옵션 |
| ToF 노이즈 | 이동평균 필터(5샘플), 비반사 매트 |
| LLM 환각 | 4단계 DSL 검증 |
| AI 서버 지연 | 노트북 비상 정지 독립 |
| 카메라 가려짐 | 두 카메라 중 하나만 보여도 동작 |

---

> 본 마스터 사양은 구현 진행에 따라 갱신된다. 각 컴포넌트의 모듈 단위 명세는
> [arduino/docs](../arduino/docs/README.md) · [ai_server/docs](../ai_server/docs/README.md) · [laptop/docs](../laptop/docs/README.md) 참조.
