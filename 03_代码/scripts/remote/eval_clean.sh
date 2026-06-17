#!/bin/bash
# M15 干净评测(单实例锁 + 统一 base 裁判,避免上次多实例污染/self-judge)。
LOCK=<REMOTE_WORKDIR>/eval_clean.lock
if [ -f "$LOCK" ]; then echo "ALREADY RUNNING, abort"; exit 0; fi
touch "$LOCK"
cd <REMOTE_WORKDIR>/gen
LOG=<REMOTE_WORKDIR>/logs/eval_clean.log
echo "=== EVAL_CLEAN START ===" > $LOG
BASE=Qwen/Qwen2.5-14B-Instruct

nuke() { nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready() { for i in $(seq 1 40); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1">>$LOG; return 0; }; sleep 15; done; echo "TIMEOUT $1">>$LOG; return 1; }

# Phase A: DoRA / IA3 merged -> 仅生成文本(之后用 base 判)
nuke; setsid bash -c "vllm serve <MODEL_DIR>/qwen14b-dora-merged --served-model-name dora --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M15.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready dora && python3 gen_text.py bundle_cell_baseline.json ans_dora.json dora 0.7 15 >> $LOG 2>&1

nuke; setsid bash -c "vllm serve <MODEL_DIR>/qwen14b-ia3-merged --served-model-name ia3 --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M15.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready ia3 && python3 gen_text.py bundle_cell_baseline.json ans_ia3.json ia3 0.7 15 >> $LOG 2>&1

# Phase B: base + dapt(lora-module) -> 统一 base 判 dora/ia3,dapt 直接 gen+base判,+ 探针
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name $BASE --enable-lora --max-lora-rank 16 --lora-modules dapt=<REMOTE_WORKDIR>/ft/qwen14b-dapt-lora --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M15.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready dapt
python3 judge_text.py ans_dora.json bundle_cell_baseline.json scores_dora.json "$BASE" >> $LOG 2>&1
python3 judge_text.py ans_ia3.json bundle_cell_baseline.json scores_ia3.json "$BASE" >> $LOG 2>&1
python3 gen_multi.py bundle_cell_baseline.json scores_dapt.json dapt "$BASE" 0.7 15 24 >> $LOG 2>&1
python3 probe_eval.py code_probe.jsonl "$BASE" probe_base.json >> $LOG 2>&1
python3 probe_eval.py code_probe.jsonl dapt probe_dapt.json >> $LOG 2>&1

nuke
rm -f "$LOCK"
echo "=== EVAL_CLEAN DONE ===" >> $LOG
