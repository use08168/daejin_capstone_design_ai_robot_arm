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
    det = f"\n노트북 탐지: {detections_json}" if detections_json else ""
    txt = ("로봇팔 작업공간 사진(좌/우)이다. 로봇팔·전선·배경 제외하고 집을 수 있는 물체 파악.\n" if images else "")
    txt += (f'사용자 명령: "{text}"{det}\n\n'
            "명령을 동작 시퀀스(DSL)로 변환하라. 직접 관절 명령(예: J1을 180도)은 set_joint, "
            "물체 집기는 vision으로 grounding. 대상 물체가 없으면 ask_user로 역질문.\n"
            f"사용 가능한 op(이 외 금지):\n{OPS_DOC}\n"
            'set_joint는 {"op":"set_joint","joint":"J1","angle":180}. target은 짧은 식별명(예: red_can). '
            'offset은 [x,y,z]mm 배열. 오직 JSON 하나: {"reasoning":"...","actions":[...]}')
    c = [{"type": "image", "image": im} for im in images] + [{"type": "text", "text": txt}]
    raw = _gen(c)
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
        text, transcript = request.text, ""
        if request.audio:
            with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
                f.write(request.audio); path = f.name
            transcript = STT.transcribe(path, language="ko", fp16=True)["text"].strip()
            os.unlink(path); text = transcript
        images = []
        for b in (request.image_left, request.image_right):
            if b:
                images.append(Image.open(io.BytesIO(b)).convert("RGB"))
        intent = route(text)
        r = pb.PlanResponse(intent=intent, transcript=transcript)
        if intent == "qa":
            r.answer = handle_qa(images, text)
        elif intent == "command":
            obj, ok, errs = handle_command(images, text, request.detections_json)
            r.dsl_json = json.dumps(obj, ensure_ascii=False); r.valid = ok; r.errors = "; ".join(errs)
        else:
            r.answer = _gen([{"type": "text", "text": text}], 128)
        r.elapsed_s = time.time() - t0
        print(f"[plan] '{text[:40]}' → {intent} ({r.elapsed_s:.1f}s)", flush=True)
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
