"""
DSL 스키마 + 검증 — LLM 무관(노트북에서도 테스트 가능).

AI 서버(LLM)는 이 DSL만 생성하고, 노트북은 이 DSL만 실행한다.
docs/5_dsl_spec.md 의 화이트리스트 op + 스키마를 코드로 구현.

여기서의 검증 = 1차(스키마·op·필수파라미터·타입·기본 시퀀스 논리).
심층 안전(워크스페이스·관절한계·충돌)은 노트북의 충돌예측 검증층 책임.
"""
import json
import re

# op → 필수 파라미터 (docs/2_grasp_place_integration.md)
#
# ▶ 상위 pick/place로 통일(2026-06-21). AI 서버(Gemma)는 "무엇을·어디로"만 결정하고,
#   "어떻게 잡을지"(접근 수직/수평 선택·파지 자세·자이로 놓기)는 노트북 MLP 런타임이 책임진다.
#   - pick  ↔ 노트북 aiGrasp(MLP 접근 자동선택 + 두 단계 집기 + 들기)
#   - place ↔ 노트북 executePlace(운반 + 자이로 수평유지 + 하강·release)
#   기존 세분화 시퀀스(move_above·descend_and_grasp·lift·move_to·release)는 이 둘로 흡수.
ALLOWED_OPS = {
    "pick":        ["target"],          # 상위 파지: target=물체 ID. opt: approach("auto"|"vert"|"horz")
    "place":       [],                  # 상위 놓기: target(장소/물체 ID) 또는 to[x,y,z] 필요. opt: offset[x,y,z]
    "set_joint":   ["joint", "angle"],  # 직접 관절 제어 (예: J1을 180도)
    "return_home": [],
    "ask_user":    ["question"],
}
APPROACHES = {"auto", "vert", "horz"}
JOINTS = {"J1", "J2", "J3", "J4", "J5", "J6", "J7"}


def _is_xyz(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(c, (int, float)) for c in v)


def _salvage_actions(text):
    """잘리거나 깨진 JSON에서 actions 배열만 복구 → {"actions":[...], "reasoning":""}.
    (예: reasoning이 길어 토큰 한계로 끊겨도 앞쪽 actions는 살림)"""
    i = text.find('"actions"')
    if i < 0:
        return None
    lb = text.find("[", i)
    if lb < 0:
        return None
    depth = 0; instr = False; esc = False; end = -1
    for j in range(lb, len(text)):           # 문자열/이스케이프 인지하며 대괄호 균형
        ch = text[j]
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
        elif ch == '"': instr = True
        elif ch == "[": depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = j; break
    arr = text[lb:end + 1] if end > 0 else None
    if arr is None:                          # 끝이 잘림 → 마지막 완전한 } 까지 모아 ] 로 닫기
        last = text.rfind("}", lb)
        if last > lb:
            arr = text[lb:last + 1] + "]"
    if not arr:
        return None
    try:
        return {"actions": json.loads(arr), "reasoning": ""}
    except Exception:
        return None


def extract_json(text):
    """LLM 출력에서 JSON 추출 — ```json 펜스/잡설 제거 후 첫 {...} 파싱. 잘리면 actions만 복구."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        raw = text[s:e + 1] if s >= 0 and e > s else text
    try:
        return json.loads(raw), None
    except Exception as e:
        salv = _salvage_actions(text)        # 잘린 출력 복구(actions 우선)
        if salv is not None:
            return salv, None
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

    holding = False                                                # pick으로 잡으면 True, place로 놓으면 False
    for i, a in enumerate(actions):
        if not isinstance(a, dict) or "op" not in a:
            errors.append(f"[{i}] op 없는 동작"); continue
        op = a["op"]
        if op not in ALLOWED_OPS:                                  # 2. 화이트리스트
            errors.append(f"[{i}] 미허용 op: {op!r}"); continue
        for p in ALLOWED_OPS[op]:                                  # 3. 필수 파라미터
            if p not in a:
                errors.append(f"[{i}] {op}: 파라미터 '{p}' 누락")
        # 3b. 타입/제약
        if op == "set_joint":
            if a.get("joint") not in JOINTS:
                errors.append(f"[{i}] joint 은 {sorted(JOINTS)} 중 하나여야 함")
            if not isinstance(a.get("angle"), (int, float)):
                errors.append(f"[{i}] angle 은 숫자여야 함")
            elif not (0 <= a["angle"] <= 180):
                errors.append(f"[{i}] angle 은 0~180 범위여야 함")
        if op == "pick" and "approach" in a and a["approach"] not in APPROACHES:
            errors.append(f"[{i}] approach 는 {sorted(APPROACHES)} 중 하나여야 함")
        if op == "place":                                          # target(의미) 또는 to[x,y,z] 중 하나는 필요
            if "target" not in a and "to" not in a:
                errors.append(f"[{i}] place: target(장소 ID) 또는 to[x,y,z] 중 하나 필요")
            if "to" in a and not _is_xyz(a["to"]):
                errors.append(f"[{i}] to 는 길이 3 숫자배열[x,y,z]이어야 함")
        if "offset" in a and not _is_xyz(a["offset"]):
            errors.append(f"[{i}] offset 은 길이 3 숫자배열이어야 함")
        if "target" in a:
            if not isinstance(a["target"], str):
                errors.append(f"[{i}] target 은 문자열(객체/장소 ID)이어야 함")
            elif known_targets is not None and a["target"] not in known_targets:
                errors.append(f"[{i}] 미탐지 target: {a['target']!r} (탐지됨: {sorted(known_targets)})")
        # 4. 기본 시퀀스 논리 — pick↔place 짝
        if op == "pick":
            if holding:
                errors.append(f"[{i}] 이미 물체를 든 상태에서 pick (먼저 place 필요)")
            holding = True
        if op == "place":
            if not holding:
                errors.append(f"[{i}] pick 없이 place (잡지 않고 놓기)")
            holding = False
    if holding:
        errors.append("마지막에 잡은 물체를 놓지 않음 (pick 후 place 필요)")
    return len(errors) == 0, errors


if __name__ == "__main__":
    # 노트북 자가 테스트 (LLM 없이) — 상위 pick/place
    good = {"reasoning": "컵을 책 위로", "actions": [
        {"op": "pick", "target": "cup_2"},                          # 접근은 노트북 MLP가 자동 결정
        {"op": "place", "target": "book_1", "offset": [0, 0, 50]},  # 책 위에 + 오프셋
        {"op": "return_home"}]}
    bad = {"actions": [
        {"op": "teleport", "target": "cup_2"},      # 미허용 op
        {"op": "pick", "target": "cup_9", "approach": "diag"},  # 미탐지 + approach 오류
        {"op": "place"}]}                            # pick 없이 + target/to 없음
    targets = {"cup_2", "book_1"}
    for name, d in [("GOOD", good), ("BAD", bad)]:
        ok, errs = validate_dsl(d, known_targets=targets)
        print(f"[{name}] ok={ok}")
        for e in errs:
            print(f"   - {e}")
    # extract_json 테스트
    obj, err = extract_json('설명...\n```json\n{"actions":[{"op":"return_home"}]}\n```\n끝')
    print("extract_json:", obj, err)
