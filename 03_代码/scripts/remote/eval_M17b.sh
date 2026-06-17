#!/bin/bash
# M17 Phase B:头条条件 n=15 重生成(Qwen-14B)+ 双独立家族裁判(Coder + internlm)。
# 目标:洗净 deep(rerank=80)头条数字 0.94 与 deep CoT,产出独立裁判 + CI。
LOCK=<REMOTE_WORKDIR>/eval_M17b.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseB
LOG=<REMOTE_WORKDIR>/logs/eval_M17b.log
echo "=== M17 PHASE-B START $(date) ===" > $LOG
# 条件 -> bundle 文件名(含 gen_prompt + gold/notes)
CONDS="baseline full_deep pecot_deep"
declare -A B=( [baseline]=bundle_werkzeug_baseline_general.json [full_deep]=bundle_werkzeug_full_general_deep.json [pecot_deep]=bundle_werkzeug_pe_cot_deep.json )

nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

# 1) Qwen-14B 生成 n=15(gen≠任何裁判)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M17b.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for c in $CONDS; do
  python3 gen_text.py ${B[$c]} ans_b_${c}.json qwen 0.7 15 24 >> $LOG 2>&1
  echo "  gen $c -> ans_b_${c}.json" >> $LOG
done

# 2) Coder-14B 判分(独立家族A)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M17b.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for c in $CONDS; do
  python3 judge_text.py ans_b_${c}.json ${B[$c]} scores_b_${c}_coderjudge.json coder >> $LOG 2>&1
  echo "  coderjudge $c" >> $LOG
done

# 3) internlm 判分(独立家族B)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M17b.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for c in $CONDS; do
  python3 judge_text.py ans_b_${c}.json ${B[$c]} scores_b_${c}_internjudge.json intern >> $LOG 2>&1
  echo "  internjudge $c" >> $LOG
done

nuke
rm -f "$LOCK"
echo "=== M17 PHASE-B DONE $(date) ===" >> $LOG
