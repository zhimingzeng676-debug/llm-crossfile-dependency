#!/bin/bash
# Archival repair: regenerate complete per-instance scores for evo_denoised
# (prior file was a 440/551 checkpoint due to a dump race). Same config, 3 conds.
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_repair.log
MP=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct; M=coder
echo "=== REPAIR START $(date) ===" >$LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo READY>>$LOG; return 0; }; sleep 12; done; echo TIMEOUT>>$LOG; return 1; }
nuke
setsid bash -c "vllm serve $MP --served-model-name $M --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/task3/vllm_repair.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready $M || { echo FAIL>>$LOG; nuke; exit 1; }
rm -f scores_evo_denoised.json scores_evo_denoised.json.log
/usr/bin/python3.10 task3_score.py instances_evo_denoised.json scores_evo_denoised.json $M no_card,static_card,static_card_humble >>$LOG 2>&1
nuke
echo "=== REPAIR DONE $(date) ===" >>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>$LOG
