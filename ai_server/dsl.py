"""
DSL 스키마 + 검증 — LLM 무관(노트북에서도 테스트 가능).

AI 서버(LLM)는 이 DSL만 생성하고, 노트북은 이 DSL만 실행한다.
docs/5_dsl_spec.md 의 화이트리스트 op + 스키마를 코드로 구현.

여기서의 검증 = 1차(스키마·op·필수파라미터·타입·기본 시퀀스 논리).
심층 안전(워크스페이스·관절한계·충돌)은 노트북의 충돌예측 검증층 책임.
"""
import json
import re

# op → 필수 파라미터 (docs/5_dsl_spec.md)
ALLOWED_OPS = {
    "set_joint":         ["joint", "angle"],   # 직접 관절 제어 (예: J1을 180도)
    "move_above":        ["target", "height_mm"],
    "descend_and_grasp": ["target"],
    "lift":              ["height_mm"],
    "move_to":           ["target", "offset"],
    "release":           [],
    "return_home":       [],
    "ask_user":          ["question"],
}
JOINTS = {"J1", "J2", "J3", "J4", "J5", "J6", "J7"}


def extract_json(text):
    """LLM 출력에서 JSON 추출 — ```json 펜스/잡설 제거 후 첫 {...} 파싱."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s:e + 1] if s >= 0 and e > s else text
    try:
        return json.loads(raw), None
    except Exception as e:
        return None, f"JSON 파싱 실패: {e}"


def validate_dsl(obj, known_targets=None):
    """DSL 1차 검증. → (ok: bool, errors: list[str]).
    known_targets: 노트북이 탐지한 객체 ID 집합(있으면 target 존재 확인)."""
    errors = []
    if not isinstance(obj, dict):
        return False, ["최상위가 객체(dict)가 아님"]
    actions = obj.get("actions")
    if not isinstance(actions, list) or not actions:
        return False, ["actions[] 누락 또는 빈 배열"]

    grasping = False
    for i, a in enumerate(actions):
        if not isinstance(a, dict) or "op" not in a:
            errors.append(f"[{i}] op 없는 동작"); continue
        op = a["op"]
        if op not in ALLOWED_OPS:                                  # 2. 화이트리스트
            errors.append(f"[{i}] 미허용 op: {op!r}"); continue
        for p in ALLOWED_OPS[op]:                                  # 3. 필수 파라미터
            if p not in a:
                errors.append(f"[{i}] {op}: 파라미터 '{p}' 누락")
        # 3b. 타입
        if op == "set_joint":
            if a.get("joint") not in JOINTS:
                errors.append(f"[{i}] joint 은 {sorted(JOINTS)} 중 하나여야 함")
            if not isinstance(a.get("angle"), (int, float)):
                errors.append(f"[{i}] angle 은 숫자여야 함")
            elif not (0 <= a["angle"] <= 180):
                errors.append(f"[{i}] angle 은 0~180 범위여야 함")
        if "height_mm" in a and not isinstance(a["height_mm"], (int, float)):
            errors.append(f"[{i}] height_mm 은 숫자여야 함")
        if "offset" in a and not (isinstance(a["offset"], list) and len(a["offset"]) == 3):
            errors.append(f"[{i}] offset 은 길이 3 배열이어야 함")
        if "target" in a:
            if not isinstance(a["target"], str):
                errors.append(f"[{i}] target 은 문자열(객체 ID)이어야 함")
            elif known_targets is not None and a["target"] not in known_targets:
                errors.append(f"[{i}] 미탐지 target: {a['target']!r} (탐지됨: {sorted(known_targets)})")
        # 4. 기본 시퀀스 논리
        if op == "descend_and_grasp":
            grasping = True
        if op == "release" and not grasping:
            errors.append(f"[{i}] grasp 없이 release")
    return len(errors) == 0, errors


if __name__ == "__main__":
    # 노트북 자가 테스트 (LLM 없이)
    good = {"reasoning": "컵을 책 위로", "actions": [
        {"op": "move_above", "target": "cup_2", "height_mm": 100},
        {"op": "descend_and_grasp", "target": "cup_2"},
        {"op": "lift", "height_mm": 100},
        {"op": "move_to", "target": "book_1", "offset": [0, 0, 50]},
        {"op": "release"},
        {"op": "return_home"}]}
    bad = {"actions": [
        {"op": "teleport", "target": "cup_2"},          # 미허용 op
        {"op": "move_above", "target": "cup_9"},          # height_mm 누락 + 미탐지
        {"op": "release"}]}                                # grasp 없이 release
    targets = {"cup_2", "book_1"}
    for name, d in [("GOOD", good), ("BAD", bad)]:
        ok, errs = validate_dsl(d, known_targets=targets)
        print(f"[{name}] ok={ok}")
        for e in errs:
            print(f"   - {e}")
    # extract_json 테스트
    obj, err = extract_json('설명...\n```json\n{"actions":[{"op":"release"}]}\n```\n끝')
    print("extract_json:", obj, err)
