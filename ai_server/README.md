# ai_server/ — AI 추론 서버

> **3계층 중 Layer 3 — "무엇을 할지" 결정.**
> 음성·이미지·자연어를 이해해 로봇이 수행할 **의도(JSON DSL)** 를 만든다. (MSI EdgeXpert에서 구동 예정)

전체 구조에서 이 폴더의 위치 → [공통 docs/architecture.md](../docs/architecture.md)

---

## 이 폴더가 하는 일 (예정)

- **Whisper Large-v3** — 한국어 음성 → 텍스트(STT)
- **Gemma 4** — 멀티모달 LLM/VLM: 명령 이해 + 객체 의미 추론(색·매칭)
- **Qwen3-Embedding-8B + FAISS** — RAG로 환각 차단, 캘리브레이션/지식 검색
- 결과를 **gRPC + Protobuf**로 노트북에 전달 → [../docs/grpc_interface.md](../docs/grpc_interface.md)

> **현황(2026-06-14):** 음성 → Whisper STT → **Gemma 4 31B** → JSON DSL → 검증 **end-to-end 작동**(실제 마이크 음성 확인, 할루시네이션 방지 입증). gRPC·비전·RAG는 다음 단계.

자세히 → 설계 [docs/README.md](docs/README.md) · **구현 명세 [docs/implementation.md](docs/implementation.md)**
