"""
05 · 전체 파이프라인 — 음성 → Whisper(STT) → Gemma 4 31B → DSL → 검증.

AI 서버의 end-to-end 흐름(gRPC·비전 제외). Whisper+Gemma를 함께 메모리에 올린다
(약 3GB+62GB < 127GB 통합메모리). 출력 DSL은 노트북의 충돌 검증층으로 넘어갈 형태.

준비: robotics/ 에 이 파일 + dsl.py. (openai-whisper, imageio-ffmpeg, transformers 5.12)
사용: python 05_pipeline.py <audio파일> [gemma모델=google/gemma-4-31B-it]
"""
import os
import sys
import time

# ffmpeg 심(sudo 없이)
import imageio_ffmpeg
_b = os.path.expanduser("~/.local/ffmpeg-shim"); os.makedirs(_b, exist_ok=True)
_l = os.path.join(_b, "ffmpeg")
if not os.path.exists(_l):
    os.symlink(imageio_ffmpeg.get_ffmpeg_exe(), _l)
os.environ["PATH"] = _b + os.pathsep + os.environ.get("PATH", "")

import torch
import whisper
from transformers import AutoProcessor
try:
    from transformers import AutoModelForMultimodalLM as AutoM
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoM

from dsl import ALLOWED_OPS, extract_json, validate_dsl

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "test_ko.mp3"
GEMMA = sys.argv[2] if len(sys.argv) > 2 else "google/gemma-4-31B-it"

OPS_DOC = "\n".join(f"  - {op}({', '.join(ps) or '없음'})" for op, ps in ALLOWED_OPS.items())
SYSTEM = f"""너는 6-DOF 로봇팔의 작업 계획기다. 사용자의 한국어 명령과 카메라가 탐지한 객체 목록을 받아,
로봇이 수행할 동작 시퀀스를 **오직 JSON 하나**로 출력한다. JSON 밖 설명 금지.
사용 가능한 동작(op)·필수 파라미터(이 외 금지):
{OPS_DOC}
규칙: 출력 {{"reasoning":"...","actions":[{{"op":...}}]}}. target은 탐지된 객체 id만(목록에 없으면 금지).
단위 mm. 집기→놓기는 move_above→descend_and_grasp→lift→move_to→release→return_home.
모호하거나 객체 없으면 ask_user. 유효 JSON 하나만."""
FEWSHOT_U = '명령: "빨간 컵을 집어서 책 위에 올려놔"\n탐지: [{"id":"cup_2","label":"cup","color":"red"},{"id":"book_1","label":"book","color":"white"}]'
FEWSHOT_A = '{"reasoning":"빨간 컵=cup_2, 책=book_1.","actions":[{"op":"move_above","target":"cup_2","height_mm":100},{"op":"descend_and_grasp","target":"cup_2"},{"op":"lift","height_mm":120},{"op":"move_to","target":"book_1","offset":[0,0,60]},{"op":"release"},{"op":"return_home"}]}'

print("[load] Whisper large-v3 …"); t0 = time.time()
stt = whisper.load_model("large-v3", device="cuda")
print(f"[load] whisper {time.time()-t0:.1f}s")
print(f"[load] Gemma {GEMMA} …"); t0 = time.time()
proc = AutoProcessor.from_pretrained(GEMMA)
gemma = AutoM.from_pretrained(GEMMA, dtype=torch.bfloat16, device_map="cuda")
print(f"[load] gemma {time.time()-t0:.1f}s")


def _m(r, t): return {"role": r, "content": [{"type": "text", "text": t}]}


def pipeline(audio, detections):
    t0 = time.time()
    text = stt.transcribe(audio, language="ko", fp16=True)["text"].strip()
    t_stt = time.time() - t0

    msgs = [_m("user", SYSTEM + "\n\n" + FEWSHOT_U), _m("model", FEWSHOT_A),
            _m("user", f'명령: "{text}"\n탐지: {detections}')]
    inputs = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                      return_dict=True, return_tensors="pt").to(gemma.device)
    t0 = time.time()
    with torch.no_grad():
        out = gemma.generate(**inputs, max_new_tokens=512, do_sample=False)
    raw = proc.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    t_gen = time.time() - t0

    obj, perr = extract_json(raw)
    ids = {d["id"] for d in detections}
    print("=" * 64)
    print(f"🎤 음성 → STT({t_stt:.1f}s): \"{text}\"")
    if perr:
        print(f"❌ {perr}\n{raw}"); return
    ok, errs = validate_dsl(obj, known_targets=ids)
    print(f"🧠 Gemma({t_gen:.1f}s) reasoning: {obj.get('reasoning','')}")
    for a in obj.get("actions", []):
        print(f"   {a}")
    print(f"✅ DSL 검증: {'통과 → 노트북 충돌검증층으로' if ok else '실패: ' + '; '.join(errs)}")


DET = [{"id": "cup_2", "label": "cup", "color": "red"},
       {"id": "book_1", "label": "book", "color": "white"},
       {"id": "pen_3", "label": "pen", "color": "blue"}]
pipeline(AUDIO, DET)
