#!/bin/bash
# 支线复现(M76):humble 识破(strict vs humble, N=103) + 跨语言 Go/Java/C(baseline vs full)。
# 同一生成器 Qwen2.5-14B,judge-independent(detect 关键词 / det gold-recall)。
cd <REMOTE_WORKDIR>
GT=<REMOTE_WORKDIR>/phaseB/gen_text.py
LOG=<REMOTE_WORKDIR>/xbranch.log
mkdir -p <REMOTE_WORKDIR>/xbranch
echo "=== XBRANCH START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 60); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
nuke
setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen14b --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/xbranch/vllm.log 2>&1" </dev/null >/dev/null 2>&1 &
if wait_ready qwen14b; then
  # 任务一:humble 识破(N=103)
  python3 $GT phaseM/bundle_strict.json <REMOTE_WORKDIR>/xbranch/ans_strict.json qwen14b 0 1 16 >> $LOG 2>&1; echo "  [DONE] strict" >> $LOG
  python3 $GT phaseM/bundle_humble.json <REMOTE_WORKDIR>/xbranch/ans_humble.json qwen14b 0 1 16 >> $LOG 2>&1; echo "  [DONE] humble" >> $LOG
  # 任务二:跨语言 Go/Java/C(baseline vs full)
  for L in go java c; do
    python3 $GT phaseD/bundle_${L}_baseline.json <REMOTE_WORKDIR>/xbranch/ans_${L}_baseline.json qwen14b 0 1 16 >> $LOG 2>&1; echo "  [DONE] ${L}_baseline" >> $LOG
    python3 $GT phaseD/bundle_${L}_full.json <REMOTE_WORKDIR>/xbranch/ans_${L}_full.json qwen14b 0 1 16 >> $LOG 2>&1; echo "  [DONE] ${L}_full" >> $LOG
  done
fi
nuke
echo "XBRANCH ALLDONE $(date)" >> $LOG
