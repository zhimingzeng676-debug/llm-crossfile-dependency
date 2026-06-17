#!/bin/bash
LOCK=<REMOTE_WORKDIR>/eval_M35.lock
[ -f "$LOCK" ] && { echo RUNNING; exit 0; }
touch "$LOCK"; cd <REMOTE_WORKDIR>/phaseM; LOG=<REMOTE_WORKDIR>/logs/eval_M35.log
echo "=== M35 PROBE START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && return 0; sleep 12; done; return 1; }
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M35.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder; python3 judge_text.py probe_answers.json probe_bundle.json scores_probe_coderjudge.json coder >> $LOG 2>&1; echo coder done>>$LOG
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M35.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern; python3 judge_text.py probe_answers.json probe_bundle.json scores_probe_internjudge.json intern >> $LOG 2>&1; echo intern done>>$LOG
nuke; rm -f "$LOCK"; echo "=== M35 PROBE DONE $(date) ===" >> $LOG
