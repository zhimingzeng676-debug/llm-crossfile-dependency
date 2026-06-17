#!/bin/bash
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_warn.log
MP=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct; M=coder
echo "=== WARN START $(date) ===" >$LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo READY>>$LOG; return 0; }; sleep 12; done; echo TIMEOUT>>$LOG; return 1; }
nuke
setsid bash -c "vllm serve $MP --served-model-name $M --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/task3/vllm_warn.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready $M || { echo FAIL>>$LOG; nuke; exit 1; }
rm -f scores_warn_orig.json scores_warn_renamed.json *.json.log
echo "=== warn orig $(date) ===" >>$LOG
/usr/bin/python3.10 task3_warn.py blindspot_dataset.json scores_warn_orig.json $M code >>$LOG 2>&1
echo "=== warn renamed $(date) ===" >>$LOG
/usr/bin/python3.10 task3_warn.py blindspot_dataset.json scores_warn_renamed.json $M code_renamed >>$LOG 2>&1
nuke
echo "=== WARN DONE $(date) ===" >>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>$LOG
