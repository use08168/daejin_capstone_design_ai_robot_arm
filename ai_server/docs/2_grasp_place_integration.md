# 2. 파지·놓기 연동 — 상위 pick/place DSL

> 📂 [루트](../../README.md) → [ai_server](../README.md) → [ai_server/docs](README.md) → **2 (pick/place 연동)**

> **이 문서의 역할.** AI 서버(Gemma)가 만드는 DSL과, 노트북이 시뮬레이터에서 완성한 **MLP 파지 + 자이로 놓기 런타임**([laptop/docs/16](../../laptop/docs/16_grasp_place_runtime.md))을 잇는 계약(contract)을 정의한다.
> **결정(2026-06-21):** 잡기/놓기를 **상위 `pick`/`place` 2개 op로 통일**한다.

---

## 1. 왜 상위 pick/place인가 — 책임 분리

기존 DSL은 잡기/놓기를 세분화된 시퀀스로 표현했다:
`move_above → descend_and_grasp → lift → move_to → release`.
이 방식은 **LLM이 "어떻게 잡을지"(접근 방향·자세·하강 깊이)까지 책임**져야 해서 ① 환각 위험이 크고 ② 노트북이 이미 학습으로 푼 문제를 LLM이 다시 떠안는 중복이었다.

우리는 시뮬에서 이 "어떻게"를 **학습·기하로 풀었다**(MLP 접근 선택·두 단계 집기·자이로 놓기). 그래서 역할을 가른다:

| 계층 | 책임 | "무엇" |
|------|------|--------|
| **AI 서버 (Gemma)** | 의미·계획 | **무엇을·어디로** — "컵을 책 위에" → `pick(cup) → place(book)` |
| **노트북 런타임 (MLP)** | 실행·기하 | **어떻게** — 수직/수평 선택·파지 자세·자이로 수평유지·충돌회피 |

→ Gemma의 출력이 단순해지고(환각 면적 ↓), 노트북의 학습 자산을 그대로 활용한다.

---

## 2. DSL 스키마 (`dsl.py`)

### 화이트리스트 op
| op | 필수 | 선택 | 의미 |
|----|------|------|------|
| `pick` | `target` | `approach`("auto"\|"vert"\|"horz") | 물체를 집어 든다. approach 생략/`auto`면 **노트북 MLP가 수직/수평 자동 결정**. |
| `place` | (target 또는 to) | `offset`[x,y,z] | 든 물체를 놓는다. `target`=장소/물체 ID(의미), `to`=명시 좌표[x,y,z]mm. |
| `set_joint` | `joint`, `angle` | — | 직접 관절 제어(디버그/교시). |
| `return_home` | — | — | 홈 자세 복귀. |
| `ask_user` | `question` | — | 모호/대상부재 시 역질문. |

> 기존 `move_above·descend_and_grasp·lift·move_to·release`는 **`pick`/`place`로 흡수·폐지**.

### 검증 규칙 (1차, `validate_dsl`)
- op 화이트리스트 + 필수 파라미터 + 타입.
- `pick.approach ∈ {auto,vert,horz}`.
- `place`는 `target`(문자열) 또는 `to`([x,y,z] 숫자) 중 **하나는 필수**, `offset`은 [x,y,z].
- `target`은 문자열이며, `known_targets` 주어지면 **탐지된 객체인지** 확인(미탐지 거부).
- **시퀀스 논리(pick↔place 짝):** `holding` 상태 추적 —
  - 든 상태에서 또 `pick` → 오류(먼저 place).
  - `pick` 없이 `place` → 오류(잡지 않고 놓기).
  - 마지막에 든 채 끝남 → 오류(놓지 않음).

> 심층 안전(워크스페이스·관절한계·충돌·페이로드)은 **노트북의 검증층** 책임. 여기는 1차 스키마/논리만.

### 표준 예시
```json
{ "reasoning": "컵을 책 위로 옮긴다",
  "actions": [
    { "op": "pick",  "target": "cup_2" },
    { "op": "place", "target": "book_1", "offset": [0, 0, 50] },
    { "op": "return_home" }
  ] }
```

---

## 3. 노트북 매핑 (실행 계약)

노트북은 `target`(의미 ID)을 스테레오 3D 좌표로 해석한 뒤 런타임을 호출한다.

| DSL | 노트북 런타임([laptop/docs/16](../../laptop/docs/16_grasp_place_runtime.md)) | 비고 |
|-----|------|------|
| `pick(target, approach)` | `aiGrasp()` — target 3D좌표·크기로 MLP 판정 → 접근(자동/강제) → `_searchObjGrasp` → `_refineWrist` → `executeGraspTwoStage` | approach=`auto`→모델 결정, `vert`/`horz`→강제. 실패 시 `ask_user`/거부 보고. |
| `place(target/to, offset)` | `executePlace()` — 목표 좌표(=target 3D + offset, 또는 to+offset) → 자이로 수평유지 운반 → 하강·release | `_held` 없으면 거부(검증에서 이미 보장). |
| `set_joint(joint, angle)` | `arm_set_angle` (3페이지) | 직접 제어 |
| `return_home` | `arm_home` | |
| `ask_user(question)` | UI 역질문 | |

> 좌표 해석: `target`이 객체면 그 객체의 3D중심, 장소면 그 위치. `place`는 보통 **그 위에 내려놓기**이므로 노트북이 안착 높이(`floorY + H/2` 등)를 적용. `offset`/`to`는 mm 단위.

---

## 4. 흐름 (end-to-end, 목표)

```
음성/텍스트 ─Whisper/Gemma─▶ route(qa|command|other)
                              └ command ─VLM grounding─▶ DSL [pick, place, ...]
                                                          │ validate_dsl(known_targets)
                                                          ▼
                              노트북: target→3D좌표 → aiGrasp/executePlace 실행
                                                          │ (런타임 충돌·도달 검증)
                                                          ▼
                                               3D 시뮬 미러 + (연동 시)실물 서보
```

---

## 5. 진행 상태 / 다음 단계
- [x] **DSL 스키마 통일** — `dsl.py`에 `pick`/`place` op·검증·시퀀스 논리 추가, 자가 테스트 통과. (이 브랜치 `ai-server/260621`)
- [x] 오케스트레이터 op 목록 자동 반영(`OPS_DOC`은 `ALLOWED_OPS`에서 생성 — 코드 변경 불필요).
- [ ] **노트북 실행 경로 배선** — `ai_plan` 수신 DSL을 4페이지 `aiGrasp`/`executePlace`로 디스패치(좌표 해석 포함).
- [ ] **end-to-end 데모** — "컵을 책 위에 놓아줘" → 시뮬에서 pick→place 자동 수행.
- [ ] 물체 **자세(orientation)** 전달(현재 위치만), 페이로드/도달 RAG grounding.

> 공통 DSL 명세([../../docs/5_dsl_spec.md](../../docs/5_dsl_spec.md))도 pick/place로 갱신 필요(후속).
