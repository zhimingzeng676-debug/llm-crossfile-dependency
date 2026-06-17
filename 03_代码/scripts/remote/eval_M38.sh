#!/bin/bash
# M38-40:大样本多语言脏依赖,5条件生成(strict/humble/baseline/humble_source/humble_prompt)。
# Qwen2.5-14B-Instruct 生成,n_runs=3。判分无关确定性指标在本地算(无需远端判分)。
# 辅助:Coder 解耦判分(gen=Qwen≠judge=Coder)strict/humble 端到端分。单实例锁。
LOCK=<REMOTE_WORKDIR>/eval_M38.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseM
LOG=<REMOTE_WORKDIR>/logs/eval_M38.log
echo "=== M38 LARGE-DIRTY START $(date) ===" > $LOG
CONDS="strict humble baseline humble_source humble_prompt"
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M38.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for c in $CONDS; do python3 gen_text.py bundle_${c}.json ans_${c}.json qwen 0.7 3 24 >> $LOG 2>&1; echo "  gen $c done">>$LOG; done

# 辅助解耦判分:Coder 判 strict/humble 端到端(gen=Qwen≠judge=Coder,红线满足)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M38.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for c in strict humble; do python3 judge_text.py ans_${c}.json bundle_${c}.json scores_${c}_coderjudge.json coder >> $LOG 2>&1; echo "  coderjudge $c done">>$LOG; done

nuke; rm -f "$LOCK"
echo "=== M38 LARGE-DIRTY DONE $(date) ===" >> $LOG
