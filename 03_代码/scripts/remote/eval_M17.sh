#!/bin/bash
# M17 Phase A:生成固定(已存答案),3裁判重判隔离 self-judge。单实例锁。
# 裁判1 Coder-14B(独立家族A);裁判2 Qwen-14B(复现self-judge作对照)。
# internlm(独立家族B)由 eval_M17_intern.sh 单独跑(等下载)。
LOCK=<REMOTE_WORKDIR>/eval_M17.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseA
LOG=<REMOTE_WORKDIR>/logs/eval_M17.log
mkdir -p <REMOTE_WORKDIR>/logs
echo "=== M17 PHASE-A START $(date) ===" > $LOG
CONDS="baseline_general full_general pe_system pe_cot pe_domain purellm_general graphcards_general"

nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
judge_all(){ # $1=served/model name  $2=tag
  for c in $CONDS; do
    python3 judge_text.py ans_werkzeug_${c}.json bundle_werkzeug.json scores_${c}_$2.json "$1" >> $LOG 2>&1
    echo "  judged $c -> scores_${c}_$2.json" >> $LOG
  done
}

# 裁判1:Coder-14B(独立家族A,gen=Qwen14B≠judge)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M17.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder && judge_all coder coderjudge

# 裁判2:Qwen-14B(self-judge 复现作对照,gen=judge=Qwen14B)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M17.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen && judge_all qwen qwenjudge

nuke
rm -f "$LOCK"
echo "=== M17 PHASE-A DONE $(date) ===" >> $LOG
