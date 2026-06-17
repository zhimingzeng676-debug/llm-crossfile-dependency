#!/bin/bash
# M22:B3 子图检索。Qwen生成,Coder+internLM双独立裁判,去循环gold。与M19 B0/B1/B2同口径。
LOCK=<REMOTE_WORKDIR>/eval_M22.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseC
LOG=<REMOTE_WORKDIR>/logs/eval_M22.log
echo "=== M22 B3 START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M22.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
python3 gen_text.py bundle_B3.json ans_B3.json qwen 0.7 10 24 >> $LOG 2>&1; echo "  gen B3">>$LOG

nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M22.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
python3 judge_text.py ans_B3.json bundle_B3.json scores_B3_coderjudge.json coder >> $LOG 2>&1; echo "  coderjudge B3">>$LOG

nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M22.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
python3 judge_text.py ans_B3.json bundle_B3.json scores_B3_internjudge.json intern >> $LOG 2>&1; echo "  internjudge B3">>$LOG

nuke
rm -f "$LOCK"
echo "=== M22 B3 DONE $(date) ===" >> $LOG
