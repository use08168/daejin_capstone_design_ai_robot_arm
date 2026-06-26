"""
07 · 오케스트레이터 — Gemma 라우터(A안)로 의도 분류 후 핸들러 분기.

흐름:
  사용자 입력 → [라우터: Gemma가 의도 분류]
                ├─ qa(상황질문)   → handle_qa: VLM이 장면 보고 답변
                ├─ command(로봇명령) → handle_command: VLM이 장면 grounding → DSL(or 역질문)
                └─ other(잡담)     → 간단 응답

핵심: AI 서버가 스스로 장면을 본다(VLM) → YOLO 라벨에만 의존하지 않음.
      명령의 대상이 실제로 보이면 DSL, 안 보이면 ask_user 역질문.
DSL의 의미 target → 3D좌표 매핑은 노트북(스테레오) 책임.

준비: robotics/ 에 이 파일 + dsl.py + cam_left.png/cam_right.png. (transformers 5.12, pillow)
사용: python 07_orchestrator.py
"""
import time

import torch
from PIL import Image
from transformers import AutoProcessor
try:
    from transformers import AutoModelForMultimodalLM as AutoM
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoM

from dsl import ALLOWED_OPS, extract_json, validate_dsl

MODEL = "google/gemma-4-31B-it"
IMAGES = [Image.open(p).convert("RGB") for p in ["cam_left.png", "cam_right.png"]]

print(f"[load] {MODEL} …"); t0 = time.time()
proc = AutoProcessor.from_pretrained(MODEL)
model = AutoM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda")
print(f"[load] {time.time()-t0:.1f}s")


def _gen(content, max_new=512):
    msgs = [{"role": "user", "content": content}]
    inputs = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                      return_dict=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new, do_sample=False)
    return proc.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def route(text):
    """Gemma 라우터(A안): 의도 분류 → JSON {intent}."""
    p = (f'사용자 입력: "{text}"\n\n'
         '이 입력의 의도를 분류하라. 오직 JSON 하나로 답하라.\n'
         '- "qa": 현재 작업공간/상황을 묻는 질문 (예: 뭐가 있어?, 빨간 거 있어?)\n'
         '- "command": 로봇팔을 움직이라는 명령 (예: ~를 집어, ~로 옮겨)\n'
         '- "other": 그 외 잡담\n'
         '형식: {"intent": "qa|command|other"}')
    obj, _ = extract_json(_gen([{"type": "text", "text": p}], 64))
    return (obj or {}).get("intent", "other")


def handle_qa(text):
    return _gen([{"type": "image", "image": im} for im in IMAGES] +
                [{"type": "text", "text":
                  "이 사진들은 로봇팔 작업공간(좌/우 카메라)이다. 로봇팔·전선·전원장치·배경은 제외하고 "
                  f"사용자 질문에 답하라: \"{text}\""}])


OPS_DOC = "\n".join(f"  - {op}({', '.join(ps) or '없음'})" for op, ps in ALLOWED_OPS.items())


def handle_command(text):
    p = ("이 사진들은 로봇팔 작업공간(좌/우 카메라)이다. 로봇팔·받침대·전선·배경은 무시하고 집을 수 있는 물체만 식별하라.\n"
         f'사용자 명령: "{text}"\n\n'
         "너는 '잡기 오케스트레이터'다. 조작 명령을 pick/place 시퀀스로 계획하라.\n"
         "1) 옮기기 = pick(집을 물체) → place(놓을 곳), 한 쌍으로. "
         "2) target은 사진에 보이는 물체의 짧은 식별명(예: red_cup, book). 대상이 안 보이면 ask_user로 되물어라. "
         "3) '어떻게 잡을지'는 노트북이 결정 → approach 생략(auto). "
         "4) place는 놓을 물체/장소 id 또는 to:[x,y,z]mm, 미세조정 offset:[x,y,z].\n"
         f"사용 가능한 op(이 외 금지):\n{OPS_DOC}\n"
         '예) {"reasoning":"빨간 컵을 책 위로","actions":[{"op":"pick","target":"red_cup"},{"op":"place","target":"book","offset":[0,0,40]}]}\n'
         '오직 JSON 하나: {"reasoning":"...","actions":[{"op":...}]}')
    raw = _gen([{"type": "image", "image": im} for im in IMAGES] + [{"type": "text", "text": p}])
    obj, perr = extract_json(raw)
    if perr:
        return f"DSL 파싱 실패: {perr}\n{raw}"
    ok, errs = validate_dsl(obj)
    lines = [f"reasoning: {obj.get('reasoning','')}"]
    for a in obj.get("actions", []):
        lines.append(f"   {a}")
    lines.append(f"검증: {'✅ 통과 → 노트북(의미target→3D좌표→충돌검증)' if ok else '❌ ' + '; '.join(errs)}")
    return "\n".join(lines)


def orchestrate(text):
    t0 = time.time(); intent = route(text); t_r = time.time() - t0
    print("=" * 64)
    print(f'🗣️  "{text}"   → 라우터({t_r:.1f}s): [{intent}]')
    t0 = time.time()
    if intent == "qa":
        ans = handle_qa(text)
    elif intent == "command":
        ans = handle_command(text)
    else:
        ans = _gen([{"type": "text", "text": text}], 128)
    print(f"⏱️ 핸들러 {time.time()-t0:.1f}s\n{ans}")


for cmd in [
    "지금 작업공간에 뭐가 있어?",          # qa
    "빨간 캔을 집어서 한쪽으로 옮겨줘",      # command (존재 → DSL)
    "노란색 공을 집어줘",                   # command (없음 → 역질문)
]:
    orchestrate(cmd)
