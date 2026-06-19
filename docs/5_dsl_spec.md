# JSON DSL 명세 — 명령 표현 언어

> **공통 합의 문서.** AI 서버(Gemma)는 이 DSL만 생성하고, 노트북은 이 DSL만 실행한다.
> `exec`/`eval` 등 임의 코드 실행은 **금지**. 사전 정의된 화이트리스트 op만 호출 가능.
> 설계 패러다임: Code-as-Policies (LLM이 제한된 DSL을 직접 생성).

---

## 1. op 카탈로그 (화이트리스트)

```python
ALLOWED_OPS = {
    "move_above":         handle_move_above,
    "descend_and_grasp":  handle_descend_and_grasp,
    "lift":               handle_lift,
    "move_to":            handle_move_to,
    "release":            handle_release,
    "return_home":        handle_return_home,
    "ask_user":           handle_ask_user,
}
```

| op | 파라미터 | 동작 |
|----|---------|------|
| `move_above` | `target`, `height_mm` | 객체 위 height_mm 위치로 이동 |
| `descend_and_grasp` | `target` | ToF 폐루프로 정밀 하강 + 그립 |
| `lift` | `height_mm` | 현재 위치에서 수직 상승 |
| `move_to` | `target`, `offset[3]` | 객체 위치 + offset으로 이동 |
| `release` | (없음) | 그리퍼 열기 |
| `return_home` | (없음) | 홈 포지션 복귀 |
| `ask_user` | `question` | 모호한 경우 사용자에게 질문 |

---

## 2. 스키마

```json
{
  "reasoning": "string (Chain-of-Thought 추론 과정)",
  "actions": [
    { "op": "move_above", "target": "cup_2", "height_mm": 100 },
    { "op": "descend_and_grasp", "target": "cup_2" },
    { "op": "lift", "height_mm": 100 },
    { "op": "move_to", "target": "book_1", "offset": [50, 0, 0] },
    { "op": "release" },
    { "op": "return_home" }
  ]
}
```

- `target`은 좌표가 아니라 **노트북이 탐지한 객체 ID**다. 좌표 해석은 노트북 책임.
- 모든 길이 단위는 mm.

---

## 3. 노트북의 4단계 검증

AI 서버 출력은 신뢰하지 않는다. 노트북은 실행 전 다음을 반드시 통과시킨다.

```python
def validate_dsl(script):
    # 1. 스키마 검증 (JSON 구조)
    if not matches_schema(script):
        return reject("스키마 오류")

    # 2. op 화이트리스트 검증
    for action in script['actions']:
        if action['op'] not in ALLOWED_OPS:
            return reject(f"unknown op: {action['op']}")

    # 3. 파라미터 안전 범위 (워크스페이스, 관절 한계, 페이로드)
    for action in script['actions']:
        if not validate_action_parameters(action):
            return reject(f"위험한 파라미터: {action}")

    # 4. 시퀀스 논리 검증 (예: grasp 없이 release, 도달 불가 등)
    if not validate_sequence_logic(script['actions']):
        return reject("비논리적 시퀀스")

    return accept()
```

| 단계 | 검증 내용 |
|------|----------|
| 1 스키마 | JSON 구조, 필수 필드 존재 |
| 2 화이트리스트 | `op`가 `ALLOWED_OPS`에 존재 |
| 3 파라미터 | 워크스페이스/관절 한계/페이로드 범위 내 |
| 4 시퀀스 논리 | 동작 순서의 물리적 타당성 |

---

## 4. 안전 규칙 (AI 서버 측 가이드)

Gemma 시스템 프롬프트에 명시:

- 페이로드 한계(150g) 초과 시 → `ask_user`로 거부
- 작업공간 외 위치 요청 → `ask_user`로 거부
- 모호한 명령 → `ask_user`로 명확화 요청
- 화이트리스트 외 op 사용 금지

> 단, AI 서버의 안전 규칙은 1차 방어선일 뿐이며 **최종 안전 보장은 노트북의 4단계 검증 + 실시간 안전 모니터**가 담당한다.

---

## 5. 컨텍스트 주입 (RAG → Gemma)

DSL 생성 시 다음 컨텍스트가 동적으로 주입된다 (값은 콜드스타트 캘리브레이션 결과를 RAG에서 조회):

```python
context = {
    "max_payload_g": 150,
    "workspace": {"x_min": -200, "x_max": 200,
                  "y_min": 50, "y_max": 350,
                  "z_min": 50, "z_max": 250},
    "joint_limits": {"J1": [-90, 90], ...},
    "detected_objects": [...],   # 노트북 YOLO-World + 삼각측량 결과
    "object_weights": {...},     # RAG object_database
}
```

---

## 6. TODO (구현 단계)

- [ ] `laptop/src/dsl/validator.py` 4단계 검증 구현
- [ ] `laptop/src/dsl/ops.py` 각 핸들러 구현
- [ ] JSON Schema 파일 정의 및 자동 검증
- [ ] AI 서버 시스템 프롬프트 ↔ 본 카탈로그 동기화 테스트
