#!/bin/bash
# M15 审计 §5:用独立 base 裁判重验 M9 Coder 跨模型 CoT 增益(原为 Coder 自判)。
# serve Coder -> gen 两条件答案文本 -> serve base -> base 判分。单实例锁。
LOCK=<REMOTE_WORKDIR>/eval_coder.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/gen
LOG=<REMOTE_WORKDIR>/logs/eval_coder.log
echo "=== EVAL_CODER START ===" > $LOG
BASE=Qwen/Qwen2.5-14B-Instruct
CODER=Qwen/Qwen2.5-Coder-14B-Instruct
nuke() { nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready() { for i in $(seq 1 40); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1">>$LOG; return 0; }; sleep 15; done; echo "TIMEOUT $1">>$LOG; return 1; }

# Phase A: Coder 生成两条件答案(仅文本)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name $CODER --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_coder.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready Coder
python3 gen_text.py bundle_werkzeug_full_general.json ans_coder_full.json "$CODER" 0.7 15 >> $LOG 2>&1
python3 gen_text.py bundle_werkzeug_pe_cot.json ans_coder_pecot.json "$CODER" 0.7 15 >> $LOG 2>&1

# Phase B: 独立 base 裁判判分
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name $BASE --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_coder.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready Qwen
python3 judge_text.py ans_coder_full.json bundle_werkzeug_full_general.json scores_coder_full_basejudge.json "$BASE" >> $LOG 2>&1
python3 judge_text.py ans_coder_pecot.json bundle_werkzeug_pe_cot.json scores_coder_pecot_basejudge.json "$BASE" >> $LOG 2>&1
nuke
rm -f "$LOCK"
echo "=== EVAL_CODER DONE ===" >> $LOG
