#!/bin/bash
# M18:去循环金标准复测。复用 Phase B 已生成的 baseline/full_deep 答案(生成固定),
# 只把金标准换成 ast独立+人工核验的去循环 gold,双独立裁判(Coder+internLM)重判。
LOCK=<REMOTE_WORKDIR>/eval_M18.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseB
LOG=<REMOTE_WORKDIR>/logs/eval_M18.log
echo "=== M18 DECOUPLED START $(date) ===" > $LOG

# 1) 把 Phase B 答案过滤到去循环金标准的 40 个 id
python3 - <<'PY' >> $LOG 2>&1
import json
ids=set(json.load(open("<REMOTE_WORKDIR>/phaseB/goldset_decoupled_ids.json")))
for cond in ("baseline","full_deep"):
    d=json.load(open(f"<REMOTE_WORKDIR>/phaseB/ans_b_{cond}.json",encoding="utf-8"))
    runs=[[c for c in run if c["id"] in ids] for run in d["runs"]]
    json.dump({"n_runs":len(runs),"runs":runs}, open(f"<REMOTE_WORKDIR>/phaseB/ansdec_{cond}.json","w",encoding="utf-8"), ensure_ascii=False)
    print(f"filtered {cond}: {len(runs[0])} cases x {len(runs)} runs")
PY

nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

# 2) Coder 独立裁判
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M18.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for c in baseline full_deep; do
  python3 judge_text.py ansdec_${c}.json goldset_decoupled.json scores_dec_${c}_coderjudge.json coder >> $LOG 2>&1
  echo "  coderjudge $c" >> $LOG
done

# 3) internLM 独立裁判
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M18.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for c in baseline full_deep; do
  python3 judge_text.py ansdec_${c}.json goldset_decoupled.json scores_dec_${c}_internjudge.json intern >> $LOG 2>&1
  echo "  internjudge $c" >> $LOG
done

nuke
rm -f "$LOCK"
echo "=== M18 DECOUPLED DONE $(date) ===" >> $LOG
