#!/bin/bash
# M44 下游危害做厚:多项目×多任务×多错法。遍历所有 bundle_*.json,Qwen 生成 n=3。
LOCK=<REMOTE_WORKDIR>/eval_M46.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseR
LOG=<REMOTE_WORKDIR>/logs/eval_M46.log
echo "=== M46 REALSTATIC START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M46.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
n=0
for b in bundle_*.json; do
  out="ans_${b#bundle_}"
  python3 gen_text.py "$b" "$out" qwen 0.7 3 24 >> $LOG 2>&1
  n=$((n+1)); echo "  [$n] gen $b done">>$LOG
done
nuke; rm -f "$LOCK"
echo "=== M46 REALSTATIC DONE $(date) total=$n ===" >> $LOG
