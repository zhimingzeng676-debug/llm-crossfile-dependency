#!/bin/bash
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_decay.log
MP=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct; M=coder
echo "=== DECAY START $(date) ===" >$LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo READY>>$LOG; return 0; }; sleep 12; done; echo TIMEOUT>>$LOG; return 1; }
nuke
setsid bash -c "vllm serve $MP --served-model-name $M --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/task3/vllm_decay.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready $M || { echo FAIL>>$LOG; nuke; exit 1; }
rm -f scores_decay_*.json scores_decay_*.json.log
for tag in cov100_p100 cov70_p100 cov50_p100 cov30_p100 cov10_p100 cov50_p50 cov30_p50 cov50_p30; do
  echo "=== deg:$tag $(date) ===" >>$LOG
  /usr/bin/python3.10 task3_opengen.py instances_decay.json scores_decay_${tag}.json $M "deg:$tag" >>$LOG 2>&1
done
nuke
echo "=== DECAY DONE $(date) ===" >>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>$LOG
