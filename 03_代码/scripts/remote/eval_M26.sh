#!/bin/bash
# M26:腾讯rapidjson baseline vs full(结构化依赖卡片)。Qwen生成,Coder+internLM双独立裁判。单实例锁。
LOCK=<REMOTE_WORKDIR>/eval_M26.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseG
LOG=<REMOTE_WORKDIR>/logs/eval_M26.log
echo "=== M26 TENCENT START $(date) ===" > $LOG
CONDS="baseline full"
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M26.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for c in $CONDS; do python3 gen_text.py bundle_tx_${c}.json ans_tx_${c}.json qwen 0.7 10 24 >> $LOG 2>&1; echo "  gen $c">>$LOG; done
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M26.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for c in $CONDS; do python3 judge_text.py ans_tx_${c}.json bundle_tx_${c}.json scores_tx_${c}_coderjudge.json coder >> $LOG 2>&1; echo "  coderjudge $c">>$LOG; done
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M26.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for c in $CONDS; do python3 judge_text.py ans_tx_${c}.json bundle_tx_${c}.json scores_tx_${c}_internjudge.json intern >> $LOG 2>&1; echo "  internjudge $c">>$LOG; done
nuke; rm -f "$LOCK"
echo "=== M26 TENCENT DONE $(date) ===" >> $LOG
