#!/bin/bash
# M15 评测编排:依次 serve 每个模型,跑 FT-only 依赖问答(n=15)+ 通用代码探针 pass@1。
# 自评估(gen=judge=同模型);merged≈base(PEFT delta<0.5%),对判分影响可忽略(文档注明)。
cd <REMOTE_WORKDIR>/gen
LOG=<REMOTE_WORKDIR>/logs/eval_all.log
echo "=== EVAL_ALL START ===" > $LOG

nuke() {
  nvidia-smi --query-compute-apps=pid --format=csv,noheader | xargs -r kill -9 2>/dev/null
  pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null
  sleep 6
}
serve() {  # $1=path $2=served-name
  nuke
  setsid bash -c "vllm serve $1 --served-model-name $2 --port 8000 --max-model-len 8192 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_eval.log 2>&1" </dev/null >/dev/null 2>&1 &
  for i in $(seq 1 40); do
    if curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null | grep -q "$2"; then echo "READY $2" >> $LOG; return 0; fi
    sleep 15
  done
  echo "TIMEOUT $2" >> $LOG; return 1
}

# base:仅探针(遗忘基线)
serve <MODEL_DIR>/Qwen2.5-14B-Instruct base
python3 probe_eval.py code_probe.jsonl base probe_base.json >> $LOG 2>&1

# DoRA / IA3:FT-only 依赖问答(自评估)
serve <MODEL_DIR>/qwen14b-dora-merged dora
python3 gen_multi.py bundle_cell_baseline.json multi_ftonly_dora.json dora dora 0.7 15 24 >> $LOG 2>&1

serve <MODEL_DIR>/qwen14b-ia3-merged ia3
python3 gen_multi.py bundle_cell_baseline.json multi_ftonly_ia3.json ia3 ia3 0.7 15 24 >> $LOG 2>&1

# DAPT:FT-only 依赖问答 + 探针(遗忘)
serve <MODEL_DIR>/qwen14b-dapt-merged dapt
python3 gen_multi.py bundle_cell_baseline.json multi_ftonly_dapt.json dapt dapt 0.7 15 24 >> $LOG 2>&1
python3 probe_eval.py code_probe.jsonl dapt probe_dapt.json >> $LOG 2>&1

nuke
echo "=== EVAL_ALL DONE ===" >> $LOG
