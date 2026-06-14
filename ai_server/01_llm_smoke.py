"""
01 · LLM 스모크 테스트 — GB10(Blackwell, sm_121)에서 transformers 생성이 실제로 되나 확인.

배경: 탐지 결과 GPU capability 12.1 > torch 2.9 지원 max 12.0 경고.
      기본 CUDA 연산이 forward-compat로 도는지, 작은 모델로 먼저 검증한다.
      성공하면 더 큰 모델(DSL 생성용)로 확장.

사용법: EdgeXpert Jupyter(robotics/)에 복붙 실행. 출력을 돌려주면 다음 단계 결정.
모델: Qwen2.5-0.5B-Instruct (~1GB, 비게이트, 빠른 다운로드). 통과하면 7B+로 상향.
"""
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

print(f"torch {torch.__version__} · CUDA available={torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"device: {torch.cuda.get_device_name(0)} · capability {torch.cuda.get_device_capability(0)}")

# ── 0. 순수 CUDA 텐서 연산부터 (커널이 도는지 최소 확인) ──
try:
    a = torch.randn(2048, 2048, device="cuda", dtype=torch.bfloat16)
    b = (a @ a).float().sum().item()
    torch.cuda.synchronize()
    print(f"[CUDA matmul] OK (sum={b:.1f}) — 기본 커널 작동")
except Exception as e:
    print(f"[CUDA matmul] 실패: {e}")
    print("→ sm_121 미지원. torch nightly(cu13) 또는 다른 백엔드 필요. 여기서 중단.")
    raise SystemExit

# ── 1. 모델 로드 ──
t0 = time.time()
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.bfloat16, device_map="cuda")
print(f"[load] {MODEL}  {time.time()-t0:.1f}s · dtype={next(model.parameters()).dtype}")

# ── 2. 생성 (로봇 명령 맥락의 간단 프롬프트) ──
msgs = [
    {"role": "system", "content": "You control a 6-DOF robot arm. Answer briefly."},
    {"role": "user", "content": "사용자가 '컵을 집어서 책 위에 올려줘'라고 했다. 어떤 동작 순서가 필요한지 한국어로 짧게 단계별로 답해라."},
]
prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to("cuda")

t0 = time.time()
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=256, do_sample=False)
dt = time.time() - t0
gen = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
ntok = out.shape[1] - inputs.input_ids.shape[1]

print(f"\n[generate] {ntok} tokens · {dt:.2f}s · {ntok/dt:.1f} tok/s")
print("-" * 60)
print(gen)
print("-" * 60)
print("\n✅ 생성 성공 — transformers 스택이 GB10에서 작동. 다음: DSL 생성 모델(7B+)로 상향.")
