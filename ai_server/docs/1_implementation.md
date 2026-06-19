# AI 서버 구현 명세 — 음성/텍스트 → DSL (EdgeXpert, warm gRPC)

> **설계 명세([README.md](README.md))의 실제 구현 기록.**
> 상태(2026-06-14): **음성/텍스트(+이미지) → STT → 의도분류 → Gemma 4 31B(VLM/DSL) → 검증 → 노트북 실행**
> end-to-end 작동. warm 상주 gRPC 서버 + 노트북 3페이지 연동 + 직접관절 실물 실행까지 검증.
> 인터페이스: [DSL 명세](../../docs/5_dsl_spec.md) · [gRPC 명세](../../docs/3_grpc_interface.md)

---

## 1. 실행 환경 (MSI EdgeXpert)

| 항목 | 값 |
|------|-----|
| 칩 | NVIDIA **GB10 Grace Blackwell**, **ARM64(aarch64)** |
| 메모리 | 128GB 통합(unified) |
| Python | 3.12 (venv `/home/use08168/jupyterlab/.venv`) |
| 딥러닝 | **torch 2.9.0+cu130**, transformers **5.12.0**, CUDA 작동 |

⚠️ **torch 빌드 취약(중요):** torch는 반드시 **2.9.0+cu130**(GB10 전용, transformers 5.12 호환). sm_121(capability 12.1)이 torch 지원(≤12.0) 밖이라 경고가 뜨나 기본 커널은 forward-compat로 작동(검증).
- pip로 다른 패키지 설치 시 torch를 끌어올려/CPU빌드로 바꿔 **환경이 깨질 수 있음** → 추가 설치는 **`--no-deps`**.
- 복구(검증): `pip install --force-reinstall torch==2.9.0 torchvision==0.24.0 --index-url https://download.pytorch.org/whl/cu130`

> 단일 GPU/통합메모리 — **무거운 작업은 하나씩만**. 서버 2개 동시 로드 시 OOM(과거 크래시 사례).

---

## 2. 개발/접속 워크플로

**SSH 키 인증**이 돼 있어 노트북에서 EdgeXpert로 직접 (복붙 불필요):
- 전송: `scp <파일> use08168@100.64.39.90:jupyterlab/robotics/`
- 실행: `ssh use08168@100.64.39.90 "cd ~/jupyterlab/robotics && /home/use08168/jupyterlab/.venv/bin/python3 <파일>"`
- 코드는 로컬 `ai_server/`에 작성·git. EdgeXpert 실행 폴더 `~/jupyterlab/robotics/`.

---

## 3. 모델

| 모델 | 역할 | 메모리 |
|------|------|:--:|
| **Whisper large-v3** | 한국어 STT(음성→텍스트). 순수 PyTorch라 GB10 호환 | ~3GB |
| **Gemma 4 31B-it** (bf16) | 멀티모달 추론 — 의도분류·**이미지(VLM)**·DSL 생성. `AutoModelForMultimodalLM`+`AutoProcessor` | ~68GB |
| Linq-Embed-Mistral 등 | (예정) RAG 임베딩 | ~14GB |

- **둘 다 warm 상주 ≈ 71GB / 127GB** (여유 56GB).
- **Gemma 4**(2026-04, Apache 2.0 무게이트): 31B는 image-text-to-text(오디오 없음) → 음성은 Whisper. "31B≈100B급" 품질.
- **양자화(4비트)**: compressed-tensors(w4a16)가 torch 빌드를 깨뜨려 현 스택 부적합 → **bf16 채택**. 추후 격리(llama.cpp GGUF).
- **캐시 정리(2026-06-14):** 테스트 모델(Qwen 0.5B·7B, Gemma E2B/12B 등) 제거 → 쓰는 모델만 남김(~77GB).

---

## 4. 아키텍처 — warm 상주 gRPC 서버 (`server.py`)

```
🎤음성/⌨️텍스트(+📷이미지) ──gRPC(50051)──▶ [AI 서버: warm]
                                              ① (음성) Whisper STT
                                              ② 라우터: 의도 분류(qa/command/other)
                                              ③ 핸들러: VLM 장면이해 / DSL 생성
                                              ④ DSL 검증(dsl.py)
   노트북(클라이언트) ◀──── 의도·답변·DSL ────┘
```

- **warm**: Gemma+Whisper를 **시작 시 1회 로드**(~7~10분, 62GB 디스크→메모리) → 이후 요청마다 **추론만**(재로드 없음).
- gRPC `RobotArmAI`: `Plan(text/audio/이미지/탐지)→PlanResponse(intent,transcript,answer,dsl,valid)`, `Health`. proto: [`shared/proto/robot_arm.proto`](../../shared/proto/robot_arm.proto).
- 노트북=클라이언트(`laptop/armvision/ai_client.py`), AI서버=서버(50051, Tailscale `100.64.39.90`).

### 4.1 오케스트레이터(라우터+핸들러)
- **라우터**: Gemma가 입력을 `qa`(상황질문)·`command`(동작명령)·`other`로 분류(JSON, ~3s).
- **qa 핸들러**: VLM이 웹캠 보고 답변(빠름 ~10s).
- **command 핸들러**: VLM 장면 grounding → DSL. 직접관절은 `set_joint`, 물체집기는 vision으로 식별. 없는 물체면 `ask_user` 역질문.

### 4.2 비전(VLM) — YOLO 보완
YOLO는 캔·스프레이를 다 'bottle'로 뭉뚱그리고 시점별 불일치 + 로봇팔 오인식. → **Gemma에 좌/우 두 시점 사진 동시 입력**:
- 로봇팔·전선·배경 제외, 집을 수 있는 물체만 **구체 식별**(빨간 에너지캔/파란 스프레이)
- 두 시점 종합(한쪽에서만 보여도 보완), 집기 전략, 없는 물체 역질문
- **역할분담**: YOLO=기하(2D박스→스테레오 3D좌표, IK용), VLM=의미(식별·추론·검증)

---

## 5. DSL + 실행

**DSL 검증(`dsl.py`, LLM 무관)** = 화이트리스트 op·필수파라미터·타입·target·시퀀스논리. op에 **`set_joint`(직접 관절)** 추가.

**실행은 노트북 책임** (3계층): DSL → 노트북 검증/안전 → 펄스. 현재:
- **`set_joint`** → 실물 실행됨 ([laptop/docs/7_ai_integration.md](../../laptop/docs/7_ai_integration.md)): 관절→채널·각도→펄스, **한 관절씩 2°램프(브라운아웃 방지)**, 3페이지 **▶ 수동 버튼+확인**(자동 아님).
- **물체집기**(move_above·grasp 등) → DSL은 생성되나 **IK 미구현으로 실행 보류**(그리퍼 입고 후).
- 심층 안전(C-space 충돌모델) 연결은 다음 단계 ([6_digital_twin_safety.md](../../laptop/docs/6_digital_twin_safety.md)).

---

## 6. 모니터링 / 로깅 (`server.py`)

서버 터미널에 **단계별 실시간 로그**(어느 모델이 어느 단계인지):
```
14:32:01 ┏━ #1 요청 수신
14:32:04 ┃ #1 🎤 STT(2.7s): "빨간 캔을 집어줘"
14:32:04 ┃ #1 📷 웹캠 2장 수신·저장
14:32:08 ┃ #1 → 의도: [command] (3.4s)
14:33:14 ┃ #1 🤖 DSL(66s) valid=True: [move_above, descend_and_grasp, ...]
14:33:14 ┗━ #1 ✅ 완료 72.1s
```
**아티팩트 저장** `~/jupyterlab/robotics/logs/`: `req####/` 음성(webm)·웹캠(jpg), `commands.jsonl`(전 명령 이력 — 시간·입력·의도·DSL·검증·소요).

---

## 7. 검증 결과 (2026-06-14)

- **NL→DSL 품질**: 같은 명령 "파란 펜 들어 홈으로" — Gemma31B만 grasp+lift 둘 다 정확(E2B·Qwen7B는 누락).
- **STT**: 실제 마이크 "빨간 컵을 잡아서 책상 위에" 정확 인식.
- **할루시네이션 방지**: "책상 없음→ask_user", 음성 "빨간 컵"인데 실제 캔→ "컵이 없고 캔이 있는데 옮길까요?" 역제안.
- **VLM(실 웹캠 2장)**: 빨간 에너지캔/파란 스프레이 구체 식별, 팔 제외, 없는 노란공 역질문, 집기전략 제시.
- **warm 서버(6시나리오)**: J1 180·J5 90→`set_joint`, "뭐있어"→qa(10s), 빨간캔→DSL(66s), 음성→STT→계획. 전부 **추론시간만**(재로드 0).
- **실물 실행**: 3페이지 ▶ → J1이 실제로 부드럽게 회전, 3D 미러 동기.

---

## 8. 설치 + 실행

```bash
# 추가 설치(이미 됨): --no-deps openai-whisper imageio-ffmpeg gTTS, grpcio grpcio-tools
# 스텁: python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. robot_arm.proto
```
**서버 켜기(한 번):** Jupyter Lab 터미널에서
```bash
bash ~/jupyterlab/robotics/run_server.sh        # 기존 서버 자동종료→로드→50051 (포그라운드=라이브 모니터링)
# 백그라운드: nohup bash run_server.sh > server.log 2>&1 &  → tail -f server.log
```
끄기: `pkill -f server.py`

| 파일 | 역할 |
|------|------|
| `server.py` | **운영 서버**(warm gRPC, 라우터·핸들러·로깅) |
| `dsl.py` | DSL 스키마·검증(LLM 무관) |
| `run_server.sh` | 한 번에 실행(중복 자동종료) |
| `client_test.py` | 점진 테스트 클라이언트 |
| `00~07_*.py` | 개발 탐색 스크립트(환경탐지·스모크·NL→DSL·STT·파이프라인·비전·오케스트레이터) |

---

## 9. 미구현 / 다음

- **그리퍼 입고 후 실제 물체 집기**(2026-06-15 예정): 물체집기 DSL → **IK(3D좌표→관절각)** → 안전(C-space 충돌) → 그리퍼 제어.
- **노트북 충돌검증층 연결**: DSL→IK→[C-space 충돌예측 모델]→실물.
- **RAG**(임베딩+FAISS), 속도 최적화(양자화), HF_TOKEN.

> 수치·결과는 2026-06-14 기준.
