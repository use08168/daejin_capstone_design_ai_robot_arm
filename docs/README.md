# docs/ — 공통 명세 & 아키텍처

> 루트 [README](../README.md)가 **"무엇을·왜"** 라면, 이 폴더는 그것을 **구체화** 한다 —
> 전체 아키텍처, 세 컴포넌트가 **왜 이렇게 나뉘는지**, 그리고 계층이 **공통으로 합의해야 하는 인터페이스 명세**.
> 한 컴포넌트 내부의 기능 명세는 각 폴더의 `docs/`에 둔다(아래 "더 깊이" 참조).

---

## 왜 3개의 폴더로 나눴나 (구조 근거)

이 프로젝트는 **3계층 분산 구조**다. 핵심 원칙: **의미 추론은 위로, 결정적·실시간 작업은 아래로.**

| 폴더 | 계층 | 존재 이유 | 핵심 |
|------|------|-----------|------|
| [`ai_server/`](../ai_server/README.md) | L3 | **"무엇을 할지"** — 음성·자연어·이미지를 이해해 의도(DSL)를 만든다. 무거운 LLM/VLM은 GPU 서버(EdgeXpert)에 둔다. | Whisper · Gemma · Qwen3 · FAISS |
| [`laptop/`](../laptop/README.md) | L2 | **"어떻게 할지"** — 의도를 비전·좌표·운동학으로 번역하고, **실시간 안전을 AI 응답에 의존하지 않고 독립 보장**한다. | YOLO-World · OpenCV · IK · Three.js 3D |
| [`arduino/`](../arduino/README.md) | L1 | **"실제 실행"** — 결정적 50Hz PWM 생성. 판단하지 않는 단순 실행자라 펌웨어가 작고 안정적. | PCA9685 · VL53L0X |

> 이렇게 나누면 ① 네트워크가 끊겨도 노트북이 **독립적으로 비상 정지**할 수 있고, ② 무거운 추론(서버)과 실시간 제어(MCU)를 분리해 각자 최적화할 수 있다. 상세 → [architecture.md](architecture.md).

```
사용자 음성 ─▶ [AI 서버] 의도(DSL) ──gRPC──▶ [노트북] 좌표·IK·안전 ──Serial──▶ [Arduino] PWM ─▶ 서보
```

---

## 공통 인터페이스 명세 (계층이 합의)

| 문서 | 내용 |
|------|------|
| [architecture.md](architecture.md) | 3계층 구조·책임 분리·통신 채널·동작 시나리오·정량 목표 |
| [system_spec.md](system_spec.md) | 시스템 마스터 사양 (전체 레퍼런스) |
| [grpc_interface.md](grpc_interface.md) | AI 서버 ↔ 노트북 gRPC/Protobuf |
| [serial_protocol.md](serial_protocol.md) | 노트북 ↔ Arduino USB Serial 패킷 |
| [dsl_spec.md](dsl_spec.md) | JSON DSL (명령 표현 언어) + 검증 |
| [conventions.md](conventions.md) | 좌표계 / 단위 / 명명 규약 |

**원칙:** 인터페이스는 **코드보다 문서를 먼저** 갱신한다. 양측 코드가 같은 문서에서 파생되므로 문서 불일치 = 통신 장애.

---

## 더 깊이 — 컴포넌트별 상세 (안으로 갈수록 구체적)

```
README.md (루트)        프로젝트 목적·기술스택·기능·현황
  └ docs/               ← 여기: 아키텍처 + 공통 인터페이스
      └ <컴포넌트>/README.md   컴포넌트 개요 + 하위 폴더 지도
          └ <컴포넌트>/docs/   기능 명세 (가장 상세)
```

- [laptop/docs](../laptop/docs/README.md) — 비전·3D 시뮬레이터·실물 연동 (기능 명세)
- [arduino/docs](../arduino/docs/README.md) — 펌웨어 (PWM·서보 캘리브레이션)
- [ai_server/docs](../ai_server/docs/README.md) — AI 추론 서버
