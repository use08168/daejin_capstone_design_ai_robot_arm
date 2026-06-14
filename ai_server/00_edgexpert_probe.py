"""
00 · EdgeXpert 환경 탐지 — AI 서버 구축 전 무엇이 깔려있나 확인.

사용법: EdgeXpert Jupyter Lab(robotics/)에 이 파일을 복붙하거나 셀에 붙여넣고 실행.
        출력 전체를 복사해 돌려주면, 그에 맞춰 LLM 서빙 방식을 정한다.

노트북(로컬)에선 의미 없음 — GPU/LLM 환경은 EdgeXpert에만 있으므로 거기서 실행.
"""
import importlib
import platform
import shutil
import subprocess
import sys


def line(t=""):
    print(t)


def run(cmd):
    """셸 명령 실행 → (성공?, 출력). 없으면 조용히 실패."""
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return out.returncode == 0, (out.stdout or out.stderr).strip()
    except Exception as e:
        return False, str(e)


def pkg(name, import_as=None):
    """패키지 설치/버전 확인."""
    try:
        m = importlib.import_module(import_as or name)
        v = getattr(m, "__version__", "?")
        return True, v
    except Exception:
        return False, None


line("=" * 60)
line("① 시스템")
line("=" * 60)
line(f"OS        : {platform.platform()}")
line(f"Python    : {sys.version.split()[0]}  ({sys.executable})")
ok, out = run("nproc")
line(f"CPU 코어  : {out if ok else '?'}")
ok, out = run("free -h | grep Mem")
line(f"RAM       : {out if ok else '?'}")
ok, out = run("df -h / | tail -1")
line(f"디스크(/) : {out if ok else '?'}")

line()
line("=" * 60)
line("② GPU / CUDA")
line("=" * 60)
ok, out = run("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader")
line(f"GPU       : {out if ok else '(nvidia-smi 없음/실패)'}")
ok, out = run("nvcc --version | tail -1")
line(f"CUDA(nvcc): {out if ok else '(없음)'}")
has_torch, tv = pkg("torch")
if has_torch:
    import torch
    line(f"torch     : {tv}  · CUDA available={torch.cuda.is_available()}"
         + (f"  · device={torch.cuda.get_device_name(0)}" if torch.cuda.is_available() else ""))
else:
    line("torch     : (미설치)")

line()
line("=" * 60)
line("③ AI/LLM 패키지")
line("=" * 60)
for name, imp in [("transformers", None), ("vllm", None), ("llama-cpp-python", "llama_cpp"),
                  ("ollama", None), ("sentence-transformers", "sentence_transformers"),
                  ("faiss-cpu", "faiss"), ("faster-whisper", "faster_whisper"),
                  ("openai-whisper", "whisper"), ("accelerate", None), ("bitsandbytes", None),
                  ("grpcio", "grpc"), ("grpcio-tools", "grpc_tools")]:
    ok, v = pkg(name, imp)
    line(f"  {'✓' if ok else '·'} {name:24s} {v or ''}")

line()
line("=" * 60)
line("④ LLM 서빙 도구")
line("=" * 60)
# Ollama
if shutil.which("ollama"):
    ok, out = run("ollama list")
    line(f"ollama 설치됨. 모델 목록:\n{out if ok else '(목록 실패 — 서비스 미실행?)'}")
else:
    line("ollama : (미설치)")
# Docker
if shutil.which("docker"):
    ok, out = run("docker ps --format '{{.Names}} ({{.Image}})'")
    line(f"docker 설치됨. 실행중 컨테이너:\n{out if ok and out else '(없음)'}")
else:
    line("docker : (미설치)")
# 허깅페이스 캐시(이미 받은 모델)
ok, out = run("ls -d ~/.cache/huggingface/hub/models--* 2>/dev/null | sed 's#.*models--##'")
line(f"HF 캐시 모델:\n{out if ok and out else '(없음)'}")

line()
line("=" * 60)
line("탐지 완료 — 이 출력 전체를 복사해 돌려주세요.")
line("=" * 60)
