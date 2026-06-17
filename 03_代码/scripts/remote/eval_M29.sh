#!/bin/bash
# M29任务一:脏场景退化。dirty full(静态卡片可能错/缺)vs baseline。Qwen生成,Coder+internLM双判。单实例锁。
LOCK=<REMOTE_WORKDIR>/eval_M29.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseI
LOG=<REMOTE_WORKDIR>/logs/eval_M29.log
echo "=== M29 DIRTY START $(date) ===" > $LOG
CONDS="baseline full"
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M29.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for c in $CONDS; do python3 gen_text.py bundle_dirty_${c}.json ans_dirty_${c}.json qwen 0.7 10 24 >> $LOG 2>&1; echo "  gen $c">>$LOG; done
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M29.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for c in $CONDS; do python3 judge_text.py ans_dirty_${c}.json bundle_dirty_${c}.json scores_dirty_${c}_coderjudge.json coder >> $LOG 2>&1; echo "  coderjudge $c">>$LOG; done
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M29.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for c in $CONDS; do python3 judge_text.py ans_dirty_${c}.json bundle_dirty_${c}.json scores_dirty_${c}_internjudge.json intern >> $LOG 2>&1; echo "  internjudge $c">>$LOG; done
nuke; rm -f "$LOCK"
echo "=== M29 DIRTY DONE $(date) ===" >> $LOG
