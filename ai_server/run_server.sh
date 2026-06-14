#!/bin/bash
# EdgeXpert AI 서버(warm gRPC) 실행 스크립트.
# Jupyter Lab 터미널에서:  bash ~/jupyterlab/robotics/run_server.sh
# 백그라운드(터미널 닫아도 유지): nohup bash ~/jupyterlab/robotics/run_server.sh > ~/jupyterlab/robotics/server.log 2>&1 &
#
# 중복 실행 방지: 기존 서버가 있으면 먼저 종료(Gemma 2개 동시 로드=메모리 초과 OOM 방지).

EXISTING=$(pgrep -f "python3 server.py")
if [ -n "$EXISTING" ]; then
  echo "[run] 기존 서버 종료(중복 방지): PID $EXISTING"
  pkill -f "python3 server.py"
  sleep 3
fi

cd ~/jupyterlab/robotics
exec /home/use08168/jupyterlab/.venv/bin/python3 server.py
