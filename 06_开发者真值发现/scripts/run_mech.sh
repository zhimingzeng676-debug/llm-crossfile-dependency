#!/bin/bash
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_mech.log
MODEL_PATH=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct
MODEL=coder
echo "=== MECH START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 60); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT">>$LOG; return 1; }
nuke
setsid bash -c "vllm serve $MODEL_PATH --served-model-name $MODEL --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/task3/vllm_mech.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready || { echo "SERVE FAIL">>$LOG; nuke; exit 1; }
echo "=== scoring mech (no_card,static_card,filler_card,random_card) $(date) ===" >>$LOG
/usr/bin/python3.10 <REMOTE_WORKDIR>/task3/task3_score.py <REMOTE_WORKDIR>/task3/instances_mech.json <REMOTE_WORKDIR>/task3/scores_mech.json $MODEL no_card,static_card,filler_card,random_card >> $LOG 2>&1
echo "=== done $(date) ===" >>$LOG
nuke
echo "=== MECH DONE $(date) ===" >>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>$LOG
