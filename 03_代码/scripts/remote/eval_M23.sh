#!/bin/bash
# M23:CPython工业级六格消融(补5格:pe/perag/ftonly/peft/all)。单实例+锁。gen≠judge。
# base+dep-lora同serve:pe/perag用base(qwen),ftonly/peft/all用dep adapter。Coder+internLM双裁判。
LOCK=<REMOTE_WORKDIR>/eval_M23.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseE
LOG=<REMOTE_WORKDIR>/logs/eval_M23.log
echo "=== M23 ABLATION START $(date) ===" > $LOG
CONDS="pe perag ftonly peft all"
declare -A GM=( [pe]=qwen [perag]=qwen [ftonly]=dep [peft]=dep [all]=dep )
declare -A GB=( [pe]=pe [perag]=perag [ftonly]=baseline [peft]=pe [all]=perag )
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

# Phase1: base + dep-lora 同serve,生成5格
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --enable-lora --max-lora-rank 32 --lora-modules dep=<REMOTE_WORKDIR>/ft/qwen14b-dep-lora --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M23.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for c in $CONDS; do
  python3 gen_text.py bundle_cpy_${GB[$c]}.json ans_cpy_${c}.json ${GM[$c]} 0.7 10 24 >> $LOG 2>&1
  echo "  gen $c (model=${GM[$c]}, bundle=${GB[$c]})" >> $LOG
done

# Phase2: Coder 判分
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M23.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for c in $CONDS; do python3 judge_text.py ans_cpy_${c}.json bundle_cpy_${GB[$c]}.json scores_cpy_${c}_coderjudge.json coder >> $LOG 2>&1; echo "  coderjudge $c">>$LOG; done

# Phase3: internLM 判分
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M23.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for c in $CONDS; do python3 judge_text.py ans_cpy_${c}.json bundle_cpy_${GB[$c]}.json scores_cpy_${c}_internjudge.json intern >> $LOG 2>&1; echo "  internjudge $c">>$LOG; done

nuke
rm -f "$LOCK"
echo "=== M23 ABLATION DONE $(date) ===" >> $LOG
