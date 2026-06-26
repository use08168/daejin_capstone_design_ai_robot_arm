# AI 서버 (MSI EdgeXpert) — 기능 명세

> **역할: "무엇을 할지" 결정.** 음성·영상을 받아 의미를 추론하고, 노트북이 실행할 JSON DSL을 생성한다.
> 결정적·실시간 작업(탐지·삼각측량·IK·안전)은 노트북 책임이며 여기서 하지 않는다.
> 인터페이스: [gRPC 명세](../../docs/3_grpc_interface.md) · 출력 형식: [DSL 명세](../../docs/5_dsl_spec.md)

### 세부 문서
| 문서 | 내용 |
|------|------|
| [1_implementation.md](1_implementation.md) | 구현 명세 — 음성/텍스트(+이미지)→STT→Gemma 4(VLM/DSL)→검증→노트북, warm gRPC |
| [2_grasp_place_integration.md](2_grasp_place_integration.md) | **파지·놓기 연동** — 상위 `pick`/`place` DSL로 통일·검증·노트북 MLP 런타임 매핑(책임 분리) |

---

## 1. 하드웨어 / 환경

| 항목 | 값 |
|------|-----|
| 디바이스 | MSI EdgeXpert |
| 칩셋 | GB10 Grace Blackwell |
| 메모리 | 128GB unified |
| 언어 | Python 3.11 |
| 통신 | gRPC 서버 (포트 50051) |

---

## 2. 구성 모델

| 모델 | 역할 | 입력 → 출력 |
|------|------|------------|
| Whisper Large-v3 | 한국어 STT | WAV → 텍스트 |
| Gemma 4 (멀티모달) | LLM 추론 + VLM | 텍스트+이미지+탐지결과 → JSON DSL |
| Qwen3-Embedding-8B | RAG 임베딩 | 텍스트 → 8192-dim 벡터 |
| FAISS | 벡터 검색 | 벡터 → 유사 지식 |

---

## 3. 기능 책임

1. **STT** — 음성(WAV)을 한국어 텍스트로 변환.
2. **객체 매칭 (VLM)** — "빨간 컵" 같은 자연어를 노트북이 보낸 탐지 객체와 매칭.
3. **속성 인식** — 색·재질·크기 등 시각 속성 추론.
4. **의도 파싱** — 사용자 명령을 단계별 동작 의도로 분해 (Chain-of-Thought).
5. **DSL 생성** — 화이트리스트 op만으로 구성된 JSON DSL 출력.
6. **RAG grounding** — 워크스페이스·관절 한계·페이로드·객체 무게 등 검증된 수치를 컨텍스트로 주입해 환각 차단.

---

## 4. 추론 절차 (Chain-of-Thought)

```
1. 명령 이해      — 무슨 동작을 원하는지
2. 객체 매칭      — 시각 데이터의 어떤 객체인지
3. 제약 검증      — 무게·도달 가능성·안전
4. 동작 계획      — 단계별 op 시퀀스
5. JSON DSL 출력
```

안전 규칙: 페이로드 초과·작업공간 외·모호한 명령은 `ask_user`로 거부/질의.
(최종 안전 보장은 노트북의 4단계 검증 + 실시간 모니터.)

---

## 5. RAG 컨텍스트 주입

콜드스타트 캘리브레이션 결과가 FAISS에 저장되어 있으며, DSL 생성 시 다음을 동적 주입:
`max_payload_g`, `workspace`, `joint_limits`, `detected_objects`, `object_weights`.

지식 베이스 스키마는 [2_system_spec.md §7](../../docs/2_system_spec.md) 참조.

---

## 6. 예정 코드 구조 (구현 단계)

```
ai_server/
├── pyproject.toml
├── src/
│   ├── main.py                 # gRPC 서버 진입점
│   ├── grpc_handler.py
│   ├── inference/
│   │   ├── whisper_stt.py
│   │   ├── gemma_llm.py
│   │   └── gemma_vlm.py
│   ├── rag/
│   │   ├── qwen_embedding.py
│   │   ├── faiss_index.py
│   │   └── knowledge_base.py
│   └── prompts/
│       ├── system_prompt.txt
│       └── examples.json
└── tests/
```

---

## 7. 단독 검증 항목 (하드웨어 없이 가능)

- [ ] EdgeXpert에서 Whisper Large-v3 한국어 STT 구동 확인
- [ ] Gemma 4 멀티모달 모델 로드 및 추론 구동 확인
- [ ] Qwen3-Embedding 임베딩 + FAISS 인덱싱 파이프라인
- [ ] 샘플 입력 → JSON DSL 생성 및 스키마 적합성 확인
