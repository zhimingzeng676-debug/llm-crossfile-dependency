#!/bin/bash
# 跨模型泛化(M74):同一 werkzeug 56 用例 + 同一 prompt bundle(baseline/full-RAG/PE-CoT),
# 仅换生成器,judge-independent det gold-recall。0 self-judge(不打分,纯字符串召回)。
cd <REMOTE_WORKDIR>/phaseB
LOG=<REMOTE_WORKDIR>/xmodel.log
mkdir -p <REMOTE_WORKDIR>/xmodel
echo "=== XMODEL START $(date) ===" > $LOG

declare -A M=(
 [qwen14b]=<MODEL_DIR>/Qwen2.5-14B-Instruct
 [intern7b]=<MODEL_DIR>/internlm2_5-7b-chat
 [llama8b]=<MODEL_DIR>/Llama-3.1-8B-Instruct
 [coder14b]=<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct
)
declare -A B=(
 [baseline]=bundle_werkzeug_baseline_general.json
 [full]=bundle_werkzeug_full_general_deep.json
 [pecot]=bundle_werkzeug_pe_cot_deep.json
)
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 70); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

for name in qwen14b intern7b llama8b coder14b; do
  echo "=== MODEL $name $(date) ===" >> $LOG
  nuke
  setsid bash -c "vllm serve ${M[$name]} --served-model-name $name --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 --trust-remote-code > <REMOTE_WORKDIR>/xmodel/vllm_$name.log 2>&1" </dev/null >/dev/null 2>&1 &
  if wait_ready $name; then
    for cond in baseline full pecot; do
      python3 gen_text.py ${B[$cond]} <REMOTE_WORKDIR>/xmodel/ans_${name}_${cond}.json $name 0 1 16 >> $LOG 2>&1
      echo "  [DONE] gen $name $cond" >> $LOG
    done
  else
    echo "  [SKIP] $name serve failed" >> $LOG
  fi
done
nuke
echo "XMODEL ALLDONE $(date)" >> $LOG
