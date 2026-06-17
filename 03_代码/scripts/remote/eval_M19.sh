#!/bin/bash
# M19:图表示梯度 B0/B1/B2。Qwen-14B 生成(gen固定模型),双独立裁判(Coder+internLM)。
# 控制变量=同焦点邻域只换卡片格式;gold=去循环(ast+人工)。
LOCK=<REMOTE_WORKDIR>/eval_M19.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseC
LOG=<REMOTE_WORKDIR>/logs/eval_M19.log
echo "=== M19 GRAPH-REP START $(date) ===" > $LOG
REPS="B0 B1 B2"
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

# 1) Qwen-14B 生成三表示答案 n=10
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct --served-model-name qwen --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M19.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready qwen
for r in $REPS; do
  python3 gen_text.py bundle_${r}.json ans_${r}.json qwen 0.7 10 24 >> $LOG 2>&1
  echo "  gen $r -> ans_${r}.json" >> $LOG
done

# 2) Coder 独立裁判
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M19.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for r in $REPS; do
  python3 judge_text.py ans_${r}.json bundle_${r}.json scores_${r}_coderjudge.json coder >> $LOG 2>&1
  echo "  coderjudge $r" >> $LOG
done

# 3) internLM 独立裁判
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M19.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for r in $REPS; do
  python3 judge_text.py ans_${r}.json bundle_${r}.json scores_${r}_internjudge.json intern >> $LOG 2>&1
  echo "  internjudge $r" >> $LOG
done

nuke
rm -f "$LOCK"
echo "=== M19 GRAPH-REP DONE $(date) ===" >> $LOG
