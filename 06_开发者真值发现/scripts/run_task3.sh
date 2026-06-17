#!/bin/bash
# Runs on A800. nuke GPU -> serve Coder-14B -> wait ready -> score 4 instance sets -> nuke.
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_task3.log
MODEL_PATH=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct
MODEL=coder
echo "=== TASK3 START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 60); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

nuke
setsid bash -c "vllm serve $MODEL_PATH --served-model-name $MODEL --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/task3/vllm.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready $MODEL || { echo "SERVE FAILED" >>$LOG; nuke; exit 1; }

for set in bugfix_denoised bugfix_raw evo_denoised evo_raw; do
  f=<REMOTE_WORKDIR>/task3/instances_${set}.json
  [ -f "$f" ] || { echo "MISSING $f" >>$LOG; continue; }
  echo "=== scoring $set $(date) ===" >>$LOG
  /usr/bin/python3.10 <REMOTE_WORKDIR>/task3/task3_score.py "$f" <REMOTE_WORKDIR>/task3/scores_${set}.json $MODEL >> $LOG 2>&1
  echo "=== done $set $(date) ===" >>$LOG
done
nuke
echo "=== TASK3 DONE $(date) ===" >>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>$LOG
