"""
03 · Gemma 4 NL→DSL — 멀티모달 모델로 자연어→DSL (02의 Gemma4 버전).

Gemma 4는 멀티모달(AutoModelForMultimodalLM/ImageTextToText + AutoProcessor)이라
02(Qwen, CausalLM+Tokenizer)와 로딩 API가 다르다. 텍스트 DSL은 동일, 검증은 dsl.py 재사용.
나중에 사진(VLM) 입력은 content에 {"type":"image"} 추가로 확장.

사용: python 03_gemma4_dsl.py [모델id]
  - API 검증: google/gemma-4-E2B-it  (~2GB, 빠름)
  - 실사용:   google/gemma-4-31B-it  (~62GB, 기본값)
준비: robotics/ 에 이 파일 + dsl.py. transformers>=5.12 필요.
"""
import sys
import time

import torch
from transformers import AutoProcessor

try:
    from transformers import AutoModelForMultimodalLM as AutoM   # Gemma4 권장 클래스
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoM

from dsl import ALLOWED_OPS, extract_json, validate_dsl

MODEL = sys.argv[1] if len(sys.argv) > 1 else "google/gemma-4-31B-it"

OPS_DOC = "\n".join(f"  - {op}({', '.join(ps) or '없음'})" for op, ps in ALLOWED_OPS.items())
SYSTEM = f"""너는 6-DOF 로봇팔의 작업 계획기다. 사용자의 한국어 명령과 카메라가 탐지한 객체 목록을 받아,
로봇이 수행할 동작 시퀀스를 **오직 JSON 하나**로 출력한다. JSON 밖 설명은 절대 쓰지 마라.

사용 가능한 동작(op)과 필수 파라미터 (이 외 금지):
{OPS_DOC}

규칙:
- 출력: {{"reasoning": "추론(한국어)", "actions": [{{"op": ..., ...}}, ...]}}
- target 은 좌표가 아니라 탐지된 객체의 id 만 사용(목록에 없는 id 금지).
- 길이 단위는 mm. 집기→놓기는 보통 move_above→descend_and_grasp→lift→move_to→release→return_home.
- 명령이 모호하거나 객체가 없으면 ask_user 로 되묻는다. 반드시 유효한 JSON 하나만 출력."""

FEWSHOT_U = '명령: "빨간 컵을 집어서 책 위에 올려놔"\n탐지: [{"id":"cup_2","label":"cup","color":"red"},{"id":"book_1","label":"book","color":"white"}]'
FEWSHOT_A = '{"reasoning":"빨간 컵=cup_2, 책=book_1.","actions":[{"op":"move_above","target":"cup_2","height_mm":100},{"op":"descend_and_grasp","target":"cup_2"},{"op":"lift","height_mm":120},{"op":"move_to","target":"book_1","offset":[0,0,60]},{"op":"release"},{"op":"return_home"}]}'

print(f"[load] {MODEL} (class={AutoM.__name__}) …")
t0 = time.time()
proc = AutoProcessor.from_pretrained(MODEL)
model = AutoM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda")
print(f"[load] {time.time()-t0:.1f}s")


def _msg(role, text):
    return {"role": role, "content": [{"type": "text", "text": text}]}


def plan(command, detections):
    # Gemma는 system 역할 대신 첫 user 턴에 지침을 넣는다(호환성).
    user0 = SYSTEM + "\n\n" + FEWSHOT_U
    msgs = [_msg("user", user0), _msg("model", FEWSHOT_A),
            _msg("user", f'명령: "{command}"\n탐지: {detections}')]
    inputs = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                      return_dict=True, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    raw = proc.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
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


DET = [{"id": "cup_2", "label": "cup", "color": "red"},
       {"id": "book_1", "label": "book", "color": "white"},
       {"id": "pen_3", "label": "pen", "color": "blue"}]
for cmd in ["빨간 컵을 집어서 책 위에 올려놔", "파란 펜을 들어서 홈으로 돌아가", "초록색 상자를 집어줘"]:
    plan(cmd, DET)
