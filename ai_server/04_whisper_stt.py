"""
04 · Whisper STT — 한국어 음성(WAV/MP3) → 텍스트.

Gemma 4 31B는 STT가 없으므로(image-text-to-text) 음성은 Whisper가 담당.
순수 PyTorch라 GB10(torch 2.9)에서 바로 작동. 출력 텍스트가 다음 단계(Gemma→DSL)의 입력.

사용: python 04_whisper_stt.py <audio파일경로> [모델=large-v3]
준비: openai-whisper + imageio-ffmpeg 설치됨. sudo 불가라 정적 ffmpeg를 PATH에 심(아래).
"""
import os
import sys
import time

# ── ffmpeg 심(sudo 없이): imageio-ffmpeg 정적 바이너리를 'ffmpeg'로 PATH 등록 ──
import imageio_ffmpeg
_exe = imageio_ffmpeg.get_ffmpeg_exe()
_bindir = os.path.expanduser("~/.local/ffmpeg-shim")
os.makedirs(_bindir, exist_ok=True)
_link = os.path.join(_bindir, "ffmpeg")
if not os.path.exists(_link):
    os.symlink(_exe, _link)
os.environ["PATH"] = _bindir + os.pathsep + os.environ.get("PATH", "")

import torch
import whisper

AUDIO = sys.argv[1] if len(sys.argv) > 1 else None
MODEL = sys.argv[2] if len(sys.argv) > 2 else "large-v3"

if not AUDIO:
    print("사용법: python 04_whisper_stt.py <audio.wav> [large-v3]")
    raise SystemExit

print(f"[load] whisper {MODEL} (cuda={torch.cuda.is_available()}) …")
t0 = time.time()
model = whisper.load_model(MODEL, device="cuda")
print(f"[load] {time.time()-t0:.1f}s")

t0 = time.time()
result = model.transcribe(AUDIO, language="ko", fp16=True)
dt = time.time() - t0

print("=" * 60)
print(f"파일: {AUDIO}   ({dt:.1f}s)")
print(f"인식 결과: {result['text'].strip()}")
print("=" * 60)
print("→ 이 텍스트를 Gemma 4(03)에 넣으면 DSL이 나온다. 다음: 음성→STT→Gemma→DSL 연결.")
