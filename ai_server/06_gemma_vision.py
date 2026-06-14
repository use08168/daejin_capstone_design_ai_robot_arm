"""
06 · Gemma 4 비전(VLM) — 웹캠 사진에서 로봇팔 제외 객체 식별 + 장면 Q&A + 역질문.

YOLO 한계 보완: YOLO는 캔·스프레이를 다 'bottle'로 뭉뚱그리고 시점별로 불일치.
Gemma 4(멀티모달)에 좌/우 두 시점 사진을 함께 줘서 종합 판단:
  ① 로봇팔(흰색 부품+ArUco)·전선·배경 제외하고 집을 수 있는 물체만, 구체적 식별
  ② 상황 질문 응답 ③ 없는 물체 역질문(할루시네이션 방지)

준비: robotics/ 에 이 파일. (transformers 5.12, pillow)
사용: python 06_gemma_vision.py <img1> [img2 ...]
"""
import sys
import time

import torch
from PIL import Image
from transformers import AutoProcessor
try:
    from transformers import AutoModelForMultimodalLM as AutoM
except ImportError:
    from transformers import AutoModelForImageTextToText as AutoM

MODEL = "google/gemma-4-31B-it"
paths = sys.argv[1:] or ["voice1.m4a"]  # 이미지 경로들
images = [Image.open(p).convert("RGB") for p in paths]
print(f"[img] {len(images)}장: {paths}")

print(f"[load] {MODEL} …"); t0 = time.time()
proc = AutoProcessor.from_pretrained(MODEL)
model = AutoM.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda")
print(f"[load] {time.time()-t0:.1f}s")


def ask(question):
    content = [{"type": "image", "image": im} for im in images] + [{"type": "text", "text": question}]
    msgs = [{"role": "user", "content": content}]
    inputs = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                      return_dict=True, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=512, do_sample=False)
    ans = proc.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    print("=" * 64)
    print(f"Q({time.time()-t0:.1f}s): {question}")
    print(f"A: {ans.strip()}")


# ① 팔 제외 객체 식별 (두 시점 종합)
ask("이 사진들은 로봇팔 작업공간을 좌/우 두 각도에서 본 것이다. "
    "흰색 3D프린트 로봇팔(검은 ArUco 마커가 붙어 있음)·전선·전원장치(검은 상자)·배경 잡동사니는 제외하고, "
    "로봇팔이 집을 수 있는 '물체'만 나열하라. 각 물체가 구체적으로 무엇인지(예: 빨간 에너지음료 캔, 파란 스프레이 병) 식별하라. "
    "두 사진을 종합해 한쪽에서만 보이는 것도 포함하라.")

# ② 역질문 (없는 물체)
ask("작업공간에 노란색 공이 있나? 없으면 대신 무엇이 있는지 알려달라.")

# ③ 집기 전략
ask("빨간 캔을 집으려면 어떤 방식으로 접근해 잡는 게 좋을지 한 문장으로 조언하라.")
