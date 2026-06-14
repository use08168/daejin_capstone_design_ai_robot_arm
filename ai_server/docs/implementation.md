# AI 서버 구현 명세 — 음성 → DSL 파이프라인 (EdgeXpert)

> **설계 명세([README.md](README.md))의 실제 구현 기록.** 무엇을 만들고, 어떤 환경에서, 무엇이 검증됐는지.
> 상태(2026-06-14): **음성 → STT → Gemma 4 31B → DSL → 검증** end-to-end 작동(실제 마이크 음성으로 확인).
> 인터페이스: [DSL 명세](../../docs/dsl_spec.md) · [gRPC 명세](../../docs/grpc_interface.md)(미구현)

---

## 1. 실행 환경 (MSI EdgeXpert)

| 항목 | 값 |
|------|-----|
| 칩 | NVIDIA **GB10 Grace Blackwell**, **ARM64(aarch64)** |
| 메모리 | 128GB 통합(unified), 가용 ~121GB |
| Python | 3.12 (venv `/home/use08168/jupyterlab/.venv`) |
| 딥러닝 | **torch 2.9.0+cu130**, transformers **5.12.0**, CUDA 작동 |

⚠️ **torch 빌드 취약(중요):** torch는 반드시 **2.9.0+cu130**(GB10 전용 빌드, transformers 5.12 호환). GPU capability **12.1(sm_121)** 이 torch 지원 범위(≤12.0)를 벗어나 경고가 뜨지만 **기본 커널은 forward-compat로 작동**(검증됨).
- pip로 다른 패키지 설치 시 torch를 끌어올리거나 CPU빌드로 바꿔 **환경이 깨질 수 있음**. 추가 설치는 **`--no-deps`** 권장.
- 복구법(검증됨): `pip install --force-reinstall torch==2.9.0 torchvision==0.24.0 --index-url https://download.pytorch.org/whl/cu130`

---

## 2. 개발 워크플로 (복붙 불필요)

코드는 로컬 `ai_server/`에 작성·git 관리. **SSH 키 인증**이 돼 있어 노트북에서 EdgeXpert로 직접:
```
로컬 ai_server/ 작성 → scp robotics/ 전송 → venv python 원격 실행 → 출력 캡처
```
- 전송: `scp <파일> use08168@100.64.39.90:jupyterlab/robotics/`
- 실행: `ssh use08168@100.64.39.90 "cd ~/jupyterlab/robotics && /home/use08168/jupyterlab/.venv/bin/python3 <파일>"`
- **로컬 LLM은 EdgeXpert에만**(노트북은 LLM 불가). LLM 의존/무관 코드 분리.

> ⚠️ 단일 GPU/통합메모리 — **무거운 작업은 하나씩만**(동시 실행 시 OOM).

---

## 3. 모델 선택

| 모델 | 역할 | 비고 |
|------|------|------|
| **Whisper large-v3** | 한국어 STT (음성→텍스트) | 순수 PyTorch라 GB10 호환. Gemma 31B엔 오디오 없어 별도 필요 |
| **Gemma 4 31B-it** (bf16) | 추론 + DSL 생성 | 멀티모달(텍스트·이미지), "31B≈100B급" 품질. `AutoModelForMultimodalLM`+`AutoProcessor` |
| (예정) 임베딩+FAISS | RAG | 캐시: Linq-Embed-Mistral 등 |

**Gemma 4** = 2026-04 출시, Apache 2.0(무게이트), 멀티모달. 12B/E2B/E4B는 오디오도 지원하나 **31B는 image-text-to-text(STT 없음)** → 음성은 Whisper 담당.

**양자화(4비트) 결론:** 속도/메모리상 매력적이나 compressed-tensors(w4a16) 경로가 torch 빌드를 깨뜨려 **현 스택엔 부적합**. **31B bf16 채택**(추론 ~24s). 최적화는 추후 격리 환경(llama.cpp GGUF) 또는 Blackwell 지원 성숙 후.

---

## 4. 파이프라인 구성 (`ai_server/`)

| 파일 | 단계 | 내용 | 실행 |
|------|:--:|------|------|
| `00_edgexpert_probe.py` | 0 | 환경 탐지(GPU·패키지·모델) | EdgeXpert |
| `01_llm_smoke.py` | 1 | sm_121 커널 + 생성 검증(Qwen 0.5B) | EdgeXpert |
| `dsl.py` | — | **DSL 스키마·검증·JSON추출 (LLM 무관)** | 노트북/EdgeXpert |
| `02_nl_to_dsl.py` | 2 | 텍스트→DSL (Qwen2.5-7B) | EdgeXpert |
| `03_gemma4_dsl.py` | 3 | 텍스트→DSL (Gemma 4, 멀티모달 API) | EdgeXpert |
| `04_whisper_stt.py` | 4 | 음성→텍스트 (ffmpeg 심 포함) | EdgeXpert |
| `05_pipeline.py` | 5 | **음성→STT→Gemma→DSL→검증 전체** | EdgeXpert |

**DSL 검증(`dsl.py`)** = 화이트리스트 op·필수 파라미터·타입·target 존재·기본 시퀀스 논리. 심층 안전(워크스페이스·관절한계·**충돌**)은 노트북 검증층 책임.

---

## 5. 검증 결과 (2026-06-14)

**NL→DSL (텍스트):** 3개 시나리오 통과. 모델별 추론 품질:

| 명령 "파란 펜을 들어서 홈으로" | 결과 |
|------|------|
| Gemma E2B | move_above→lift→home (grasp 누락) |
| Qwen 7B | move_above→grasp→home (lift 누락) |
| **Gemma 31B** | move_above→**grasp→lift**→home (정확) |

**STT (Whisper large-v3):**
- 합성음(gTTS): "빨간 컵을 집어서 책 위에 올려줘" 정확 인식(1.2s)
- **실제 마이크**: "빨간 컵을 잡아서 책상 위에 올려줘" 정확 인식(1.4s)

**전체 파이프라인 (실제 음성, end-to-end):**
```
🎤 voice1.m4a → STT(2.7s): "빨간 컵을 잡아서 책상 위에 올려줘."
🧠 Gemma 31B(23.9s): "빨간 컵=cup_2. 하지만 탐지목록에 '책상'이 없음 → 확인 필요"
   → ask_user("책상 위치를 찾을 수 없습니다. 어디에 올려둘까요?")
✅ DSL 검증 통과
```
→ **실환경 할루시네이션 방지 입증:** 탐지 안 된 '책상'을 지어내지 않고 되물음. (탐지에 있는 객체("책 위에")는 정상 6단계 시퀀스 생성.)

성능: Gemma 로드 ~435s(캐시), Whisper 로드 ~10s, 추론 STT 2.7s + Gemma 24s ≈ 27s/명령.

---

## 6. 설치 절차 (EdgeXpert venv)

```bash
# 이미 있음: torch 2.9.0+cu130, transformers 5.12, accelerate, bitsandbytes
pip install --no-deps openai-whisper imageio-ffmpeg   # STT + ffmpeg(sudo 없이)
pip install --no-deps gTTS                              # (테스트용 합성음)
# Gemma 4 / Whisper 모델은 첫 실행 시 자동 다운로드(HF)
```
> ffmpeg는 sudo 불가라 imageio-ffmpeg 정적 바이너리를 런타임에 PATH 심(04/05 내장).

---

## 7. 미구현 / 다음

- **gRPC 서버**(포트 50051) — 노트북이 음성·탐지를 보내 DSL 받기. [grpc_interface.md](../../docs/grpc_interface.md)
- **비전(VLM)** — Gemma 4에 카메라 이미지 입력("왼쪽 컵 옆 책" 같은 공간 추론, 표면 위치 등)
- **RAG** — 임베딩+FAISS로 워크스페이스/한계 수치 grounding
- **노트북 충돌검증층 연결** — DSL→IK→[C-space 충돌예측 모델]→실물 ([../../laptop/docs/digital_twin_safety.md](../../laptop/docs/digital_twin_safety.md))
- 속도 최적화(양자화), HF_TOKEN 설정(다운로드 속도)

> 수치·결과는 2026-06-14 기준. 환경 변경 시 재검증.
