"""
AI 서버 (gRPC, warm 상주) — Gemma 4 31B + Whisper를 시작 시 1회 로드하고 대기.
요청(Plan)마다 추론만 → 빠른 응답. 노트북=클라이언트, 이 서버=50051.

흐름: (음성 있으면 STT) → 라우터(qa/command/other) → 핸들러 → 응답/DSL(검증).
준비: robotics/ 에 server.py + dsl.py + robot_arm_pb2{,_grpc}.py(protoc 생성) + cam은 요청으로 전달.
실행: python server.py   (로드 ~7분 후 'gRPC serving on 50051')
"""
import io
import json
import os
import tempfile
import time
from concurrent import futures
from datetime import datetime

# ffmpeg 심(whisper m4a 디코딩, sudo 없이)
import imageio_ffmpeg
_b = os.path.expanduser("~/.local/ffmpeg-shim"); os.makedirs(_b, exist_ok=True)
_l = os.path.join(_b, "ffmpeg")
if not os.path.exists(_l):
    os.symlink(imageio_ffmpeg.get_ffmpeg_exe(), _l)
os.environ["PATH"] = _b + os.pathsep + os.environ.get("PATH", "")

import grpc
import torch
import whisper
from PIL import Image
from transformers import AutoProcessor
try:
    from transformers import AutoModelForMultimodalLM as AutoM
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoM

import robot_arm_pb2 as pb
import robot_arm_pb2_grpc as pbg
from dsl import ALLOWED_OPS, extract_json, validate_dsl

GEMMA = "google/gemma-4-31B-it"
OPS_DOC = "\n".join(f"  - {op}({', '.join(ps) or '없음'})" for op, ps in ALLOWED_OPS.items())

# ── 로깅/아티팩트: 명령·음성·사진·결과를 logs/ 에 남기고 터미널에 단계별 출력 ──
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
_REQ = [0]


def log(msg):
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)

print("[server] Whisper large-v3 로드 …", flush=True); t0 = time.time()
STT = whisper.load_model("large-v3", device="cuda")
print(f"[server] whisper {time.time()-t0:.0f}s", flush=True)
print("[server] Gemma 4 31B 로드 …", flush=True); t0 = time.time()
PROC = AutoProcessor.from_pretrained(GEMMA)
GM = AutoM.from_pretrained(GEMMA, dtype=torch.bfloat16, device_map="cuda")
print(f"[server] gemma {time.time()-t0:.0f}s · 모델 준비 완료(warm)", flush=True)


def _gen(content, max_new=512):
    msgs = [{"role": "user", "content": content}]
    inp = PROC.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                   return_dict=True, return_tensors="pt").to(GM.device)
    with torch.no_grad():
        out = GM.generate(**inp, max_new_tokens=max_new, do_sample=False)
    return PROC.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def route(text):
    p = (f'사용자 입력: "{text}"\n오직 JSON 하나로 의도 분류:\n'
         '- "qa": 작업공간/상황 질문\n- "command": 로봇팔 동작 명령\n- "other": 잡담\n'
         '{"intent":"qa|command|other"}')
    obj, _ = extract_json(_gen([{"type": "text", "text": p}], 64))
    return (obj or {}).get("intent", "other")


def handle_qa(images, text):
    c = [{"type": "image", "image": im} for im in images]
    c.append({"type": "text", "text":
              ("이 사진들은 로봇팔 작업공간이다. 로봇팔·전선·전원장치·배경은 제외하고 "
               f'질문에 답하라: "{text}"') if images else f'질문에 답하라: "{text}"'})
    return _gen(c)


def handle_command(images, text, detections_json):
    """잡기 오케스트레이터 — 조작 명령을 pick/place 시퀀스로 계획.
    '무엇을·어디로'만 결정하고, '어떻게 잡을지'(수직/수평·자세)는 노트북 MLP 런타임이 담당."""
    det = f"\n노트북 YOLO 탐지: {detections_json}" if detections_json else ""
    seen = ("로봇팔 작업공간 사진(좌/우)이다. 로봇팔·받침대·전선·전원·배경은 무시하고, 집을 수 있는 물체만 식별하라.\n" if images else "")
    txt = (seen +
           f'사용자 명령: "{text}"{det}\n\n'
           "너는 로봇팔의 '잡기 오케스트레이터'다. 조작 명령을 pick/place 시퀀스로 계획하라.\n"
           "규칙:\n"
           "1) 물체를 옮기는 명령 = pick(집을 물체) → place(놓을 곳). 반드시 한 쌍으로(잡으면 놓기).\n"
           "2) target 은 장면에 실제로 보이는 물체의 짧은 식별명(예: red_cup, book). "
           "명령의 대상 물체가 사진에 안 보이면 DSL 대신 ask_user로 되물어라.\n"
           "3) '어떻게 잡을지'(수직/수평·손목 자세)는 노트북이 결정한다 → approach 는 보통 생략(auto).\n"
           "4) place 는 놓을 물체/장소 id(그 위에 놓기) 또는 to:[x,y,z](mm). 미세조정은 offset:[x,y,z].\n"
           "5) 직접 관절 제어만 요구하면(예: J1을 180도) set_joint.\n"
           f"사용 가능한 op(이 외 금지):\n{OPS_DOC}\n"
           "⚠ actions 를 먼저 쓰고, reasoning 은 마지막에 한 문장으로 아주 짧게(생략 가능).\n"
           '예) {"actions":[{"op":"pick","target":"red_cup"},{"op":"place","target":"book","offset":[0,0,40]}],"reasoning":"컵을 책 위로"}\n'
           '예) {"actions":[{"op":"ask_user","question":"노란 공이 안 보여요. 어디 있나요?"}]}\n'
           '오직 JSON 하나만 출력: {"actions":[...],"reasoning":"짧게"}')
    c = [{"type": "image", "image": im} for im in images] + [{"type": "text", "text": txt}]
    raw = _gen(c, max_new=1024)   # reasoning 잘림 방지(여유 토큰)
    obj, perr = extract_json(raw)
    if perr:
        return {"reasoning": "", "actions": []}, False, [perr]
    ok, errs = validate_dsl(obj)
    return obj, ok, errs


class Servicer(pbg.RobotArmAIServicer):
    def Health(self, request, context):
        return pb.HealthResponse(models_ready=True, info="gemma-4-31B + whisper-large-v3 warm")

    def Plan(self, request, context):
        t0 = time.time()
        _REQ[0] += 1; rid = _REQ[0]
        adir = os.path.join(LOG_DIR, f"req{rid:04d}_{datetime.now():%H%M%S}")
        os.makedirs(adir, exist_ok=True)
        log(f"┏━ #{rid} 요청 수신 ━━━━━━━━━━━━━━")

        # 1) 입력 (음성→STT 또는 텍스트)
        text, transcript = request.text, ""
        if request.audio:
            open(os.path.join(adir, "voice.webm"), "wb").write(request.audio)  # 음성 저장
            log(f"┃ #{rid} 🎤 음성 {len(request.audio)//1024}KB → Whisper STT 처리 중…")
            ts = time.time()
            with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
                f.write(request.audio); path = f.name
            transcript = STT.transcribe(path, language="ko", fp16=True)["text"].strip()
            os.unlink(path); text = transcript
            log(f"┃ #{rid} 🎤 STT({time.time()-ts:.1f}s): \"{transcript}\"")
        else:
            log(f"┃ #{rid} ⌨️  텍스트: \"{text}\"")

        # 2) 이미지(웹캠) 저장
        images = []
        for b, nm in ((request.image_left, "cam_left.jpg"), (request.image_right, "cam_right.jpg")):
            if b:
                open(os.path.join(adir, nm), "wb").write(b)
                images.append(Image.open(io.BytesIO(b)).convert("RGB"))
        if images:
            log(f"┃ #{rid} 📷 웹캠 {len(images)}장 수신·저장")

        # 3) 의도 분류
        log(f"┃ #{rid} 🧠 Gemma 의도 분류 중…")
        ts = time.time(); intent = route(text)
        log(f"┃ #{rid} → 의도: [{intent}] ({time.time()-ts:.1f}s)")

        # 4) 핸들러
        r = pb.PlanResponse(intent=intent, transcript=transcript)
        ts = time.time()
        if intent == "qa":
            log(f"┃ #{rid} 🧠 Gemma 장면 분석(VLM){' · 이미지'+str(len(images))+'장' if images else ''} 중…")
            r.answer = handle_qa(images, text)
            log(f"┃ #{rid} 💬 답변({time.time()-ts:.1f}s): {r.answer[:70]}")
        elif intent == "command":
            log(f"┃ #{rid} 🧠 Gemma DSL 생성{' · 이미지분석' if images else ''} 중…")
            obj, ok, errs = handle_command(images, text, request.detections_json)
            r.dsl_json = json.dumps(obj, ensure_ascii=False); r.valid = ok; r.errors = "; ".join(errs)
            acts = ", ".join(a.get("op", "?") for a in obj.get("actions", []))
            log(f"┃ #{rid} 🤖 DSL({time.time()-ts:.1f}s) valid={ok}: [{acts}]")
            if errs:
                log(f"┃ #{rid} ⚠ 검증오류: {r.errors}")
        else:
            r.answer = _gen([{"type": "text", "text": text}], 128)
            log(f"┃ #{rid} 💬 잡담 응답({time.time()-ts:.1f}s)")

        r.elapsed_s = time.time() - t0
        # 5) 명령 로그 append (재현·분석용)
        rec = {"time": datetime.now().isoformat(timespec="seconds"), "req": rid,
               "source": "voice" if request.audio else "text", "input": text,
               "intent": intent, "answer": r.answer, "dsl": r.dsl_json, "valid": r.valid,
               "errors": r.errors, "images": len(images), "elapsed_s": round(r.elapsed_s, 1)}
        with open(os.path.join(LOG_DIR, "commands.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log(f"┗━ #{rid} ✅ 완료 {r.elapsed_s:.1f}s  (logs/{os.path.basename(adir)})")
        return r


def serve():
    s = grpc.server(futures.ThreadPoolExecutor(max_workers=2),
                    options=[("grpc.max_receive_message_length", 32 * 1024 * 1024)])
    pbg.add_RobotArmAIServicer_to_server(Servicer(), s)
    s.add_insecure_port("[::]:50051")
    s.start(); print("[server] gRPC serving on 50051 (warm, 대기중)", flush=True)
    s.wait_for_termination()


if __name__ == "__main__":
    serve()
