#!/bin/bash
# M42b 强制猜测baseline(去abstain混淆):seen/unseen forced,Qwen n=3。测纯记忆贡献。
LOCK=<REMOTE_WORKDIR>/eval_M42b.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseN
LOG=<REMOTE_WORKDIR>/logs/eval_M42b.log
echo "=== M42b FORCED START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M42b.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for c in seen_baseline_forced unseen_baseline_forced; do python3 gen_text.py bundle_${c}.json ans_${c}.json qwen 0.7 3 24 >> $LOG 2>&1; echo "  gen $c done">>$LOG; done
nuke; rm -f "$LOCK"
echo "=== M42b FORCED DONE $(date) ===" >> $LOG
