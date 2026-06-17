#!/bin/bash
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_cc.log
MP=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct; M=coder
echo "=== CC START $(date) ===" >$LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo READY>>$LOG; return 0; }; sleep 12; done; echo TIMEOUT>>$LOG; return 1; }
nuke
setsid bash -c "vllm serve $MP --served-model-name $M --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/task3/vllm_cc.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready $M || { echo FAIL>>$LOG; nuke; exit 1; }
rm -f scores_cc_*.json scores_cc_*.json.log
for cond in open_staticcard open_static_cochange open_static_filler; do
  echo "=== $cond $(date) ===" >>$LOG
  /usr/bin/python3.10 task3_opengen.py instances_cc.json scores_cc_${cond}.json $M $cond >>$LOG 2>&1
done
nuke
echo "=== CC DONE $(date) ===" >>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>$LOG
