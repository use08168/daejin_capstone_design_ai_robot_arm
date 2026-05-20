# 공통 docs

> 여러 계층(AI 서버 · 노트북 · Arduino)이 **공통으로 합의해야 하는 명세**를 모은다.
> 한 계층만의 내부 기능 명세는 각 컴포넌트 폴더의 `docs/`에 둔다.

## 문서 목록

| 문서 | 내용 |
|------|------|
| [system_spec.md](system_spec.md) | 시스템 마스터 사양 (전체 레퍼런스) |
| [architecture.md](architecture.md) | 3계층 분산 구조, 책임 분리, 정량 목표 |
| [grpc_interface.md](grpc_interface.md) | AI 서버 ↔ 노트북 gRPC/Protobuf 명세 |
| [serial_protocol.md](serial_protocol.md) | 노트북 ↔ Arduino USB Serial 패킷 명세 |
| [dsl_spec.md](dsl_spec.md) | JSON DSL (명령 표현 언어) 명세 + 검증 |
| [conventions.md](conventions.md) | 좌표계 / 단위 / 명명 규약 |

## 원칙

- **인터페이스 변경 시 코드보다 문서를 먼저 갱신한다.** 양측 코드가 같은 문서에서 파생되므로, 문서 불일치는 곧 통신 장애다.
- 컴포넌트별 기능 명세는 각각:
  - [arduino/docs](../arduino/docs/README.md) — 펌웨어
  - [ai_server/docs](../ai_server/docs/README.md) — AI 추론 서버
  - [laptop/docs](../laptop/docs/README.md) — 제어 허브
