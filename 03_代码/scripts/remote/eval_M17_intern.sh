#!/bin/bash
# M17 Phase A 裁判3:internlm2_5-7b-chat(独立家族B,非 Qwen 血统)。生成固定,judge_text 重判 7 条件。
LOCK=<REMOTE_WORKDIR>/eval_M17i.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseA
LOG=<REMOTE_WORKDIR>/logs/eval_M17_intern.log
echo "=== M17 INTERN START $(date) ===" > $LOG
CONDS="baseline_general full_general pe_system pe_cot pe_domain purellm_general graphcards_general"
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M17i.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for c in $CONDS; do
  python3 judge_text.py ans_werkzeug_${c}.json bundle_werkzeug.json scores_${c}_internjudge.json intern >> $LOG 2>&1
  echo "  judged $c -> scores_${c}_internjudge.json" >> $LOG
done
nuke
rm -f "$LOCK"
echo "=== M17 INTERN DONE $(date) ===" >> $LOG
