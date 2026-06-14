"""
02 · NL→DSL 프로토타입 — 자연어 명령 → JSON DSL 생성·검증.

AI 서버의 핵심: 사용자 명령 + 탐지된 객체 → 화이트리스트 op의 동작 시퀀스(DSL).
LLM(EdgeXpert)이 생성하고, dsl.py(LLM 무관)가 검증. 심층 안전은 노트북 책임.

준비: robotics/ 에 이 파일 + dsl.py 둘 다 두기(Jupyter 파일 업로드).
모델: Qwen2.5-7B-Instruct (bf16, ~15GB). 통합메모리 크니 14B/32B로 상향 가능.
"""
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from dsl import ALLOWED_OPS, extract_json, validate_dsl

MODEL = "Qwen/Qwen2.5-7B-Instruct"

# ── 시스템 프롬프트: DSL 명세를 모델에 주입 ──
OPS_DOC = "\n".join(f"  - {op}({', '.join(ps) or '없음'})" for op, ps in ALLOWED_OPS.items())
SYSTEM = f"""너는 6-DOF 로봇팔의 작업 계획기다. 사용자의 한국어 명령과 카메라가 탐지한 객체 목록을 받아,
로봇이 수행할 동작 시퀀스를 **오직 JSON 하나**로 출력한다. JSON 밖 설명은 절대 쓰지 마라.

사용 가능한 동작(op)과 필수 파라미터 (이 외 금지):
{OPS_DOC}

규칙:
- 출력 형식: {{"reasoning": "추론(한국어)", "actions": [{{"op": ..., ...}}, ...]}}
- target 은 좌표가 아니라 **탐지된 객체의 id** 만 사용(목록에 없는 id 금지).
- 모든 길이 단위는 mm.
- 집기→놓기는 보통: move_above → descend_and_grasp → lift → move_to → release → return_home.
- 명령이 모호하면 ask_user 로 되묻는다.
- 반드시 유효한 JSON 하나만 출력."""

FEWSHOT_U = """명령: "빨간 컵을 집어서 책 위에 올려놔"
탐지된 객체: [{"id":"cup_2","label":"cup","color":"red"}, {"id":"book_1","label":"book","color":"white"}]"""
FEWSHOT_A = """{"reasoning": "빨간 컵은 cup_2, 책은 book_1. 컵을 집어 책 위에서 놓는다.", "actions": [{"op":"move_above","target":"cup_2","height_mm":100},{"op":"descend_and_grasp","target":"cup_2"},{"op":"lift","height_mm":120},{"op":"move_to","target":"book_1","offset":[0,0,60]},{"op":"release"},{"op":"return_home"}]}"""

print(f"[load] {MODEL} …")
t0 = time.time()
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda")
print(f"[load] {time.time()-t0:.1f}s")


def plan(command, detections):
    user = f'명령: "{command}"\n탐지된 객체: {detections}'
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": FEWSHOT_U}, {"role": "assistant", "content": FEWSHOT_A},
            {"role": "user", "content": user}]
    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt").to("cuda")
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    raw = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    dt = time.time() - t0

    ids = {d["id"] for d in detections}
    obj, perr = extract_json(raw)
    print("=" * 64)
    print(f'명령: "{command}"   ({dt:.1f}s)')
    if perr:
        print(f"❌ {perr}\n원문:\n{raw}"); return
    ok, errs = validate_dsl(obj, known_targets=ids)
    print(f"reasoning: {obj.get('reasoning','')}")
    for a in obj.get("actions", []):
        print(f"   {a}")
    print(f"검증: {'✅ 통과' if ok else '❌ ' + '; '.join(errs)}")


# ── 테스트 시나리오 ──
DET = [{"id": "cup_2", "label": "cup", "color": "red"},
       {"id": "book_1", "label": "book", "color": "white"},
       {"id": "pen_3", "label": "pen", "color": "blue"}]
for cmd in [
    "빨간 컵을 집어서 책 위에 올려놔",
    "파란 펜을 들어서 홈으로 돌아가",
    "초록색 상자를 집어줘",          # 탐지에 없음 → ask_user 기대
]:
    plan(cmd, DET)
