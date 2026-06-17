#!/bin/bash
# 跨模型 LLM-judge 辅口径(0 self-judge):internlm 判 qwen14b+coder14b,coder 判 intern7b。
cd <REMOTE_WORKDIR>/phaseB
LOG=<REMOTE_WORKDIR>/xmodel_judge.log
echo "=== XJUDGE START $(date) ===" > $LOG
declare -A BUN=(
 [baseline]=bundle_werkzeug_baseline_general.json
 [full]=bundle_werkzeug_full_general_deep.json
 [pecot]=bundle_werkzeug_pe_cot_deep.json
)
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 60); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
judge_set(){ # $1=judge served-name  $2...=gen models
  local J=$1; shift
  for m in "$@"; do
    for cond in baseline full pecot; do
      python3 judge_text.py <REMOTE_WORKDIR>/xmodel/ans_${m}_${cond}.json ${BUN[$cond]} <REMOTE_WORKDIR>/xmodel/jscore_${m}_${cond}.json $J 16 >> $LOG 2>&1
      echo "  [DONE] judge $m $cond by $J" >> $LOG
    done
  done
}
# judge1: internlm 判 qwen14b, coder14b(gen≠judge)
nuke
setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name internjudge --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 --trust-remote-code > <REMOTE_WORKDIR>/xmodel/vllm_internjudge.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready internjudge && judge_set internjudge qwen14b coder14b
# judge2: coder 判 intern7b(gen≠judge)
nuke
setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coderjudge --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 --trust-remote-code > <REMOTE_WORKDIR>/xmodel/vllm_coderjudge.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coderjudge && judge_set coderjudge intern7b
nuke
echo "XJUDGE ALLDONE $(date)" >> $LOG
