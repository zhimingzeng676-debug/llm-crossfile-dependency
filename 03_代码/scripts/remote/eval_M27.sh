#!/bin/bash
# M27:新工作去循环重判。复用M20/21已有答案(生成固定),只换独立去循环gold,Coder+internLM双判。单实例锁。
LOCK=<REMOTE_WORKDIR>/eval_M27.lock
[ -f "$LOCK" ] && { echo "RUNNING"; exit 0; }
touch "$LOCK"
cd <REMOTE_WORKDIR>/phaseH
LOG=<REMOTE_WORKDIR>/logs/eval_M27.log
echo "=== M27 DECOUPLE-V2 START $(date) ===" > $LOG
# proj -> 答案前缀(原始）
declare -A ANS=( [lua]=ans_c [gson]=ans_java [go]=ans_go [cpy]=ans_cpy )
PROJS="lua gson go cpy"

# 1) 过滤答案到解耦bundle的ids
for p in $PROJS; do
python3 - "$p" "${ANS[$p]}" <<'PY' >> $LOG 2>&1
import json,sys
p,ansp=sys.argv[1],sys.argv[2]
ids=set(x["id"] for x in json.load(open(f"<REMOTE_WORKDIR>/phaseH/bundle_{p}_dec.json",encoding="utf-8")))
for cond in ("baseline","full"):
    d=json.load(open(f"<REMOTE_WORKDIR>/phaseH/{ansp}_{cond}.json",encoding="utf-8"))
    runs=[[c for c in run if c["id"] in ids] for run in d["runs"]]
    json.dump({"n_runs":len(runs),"runs":runs}, open(f"<REMOTE_WORKDIR>/phaseH/ansdec_{p}_{cond}.json","w",encoding="utf-8"), ensure_ascii=False)
    print(f"filter {p} {cond}: {len(runs[0])} cases")
PY
done

nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 50); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }

# 2) Coder 判
nuke; setsid bash -c "vllm serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct --served-model-name coder --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M27.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready coder
for p in $PROJS; do for c in baseline full; do
  python3 judge_text.py ansdec_${p}_${c}.json bundle_${p}_dec.json scores_dec27_${p}_${c}_coderjudge.json coder >> $LOG 2>&1; echo "  coderjudge ${p}_${c}">>$LOG
done; done

# 3) internLM 判
nuke; setsid bash -c "vllm serve <MODEL_DIR>/internlm2_5-7b-chat --served-model-name intern --trust-remote-code --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 > <REMOTE_WORKDIR>/logs/vllm_M27.log 2>&1" </dev/null >/dev/null 2>&1 &
wait_ready intern
for p in $PROJS; do for c in baseline full; do
  python3 judge_text.py ansdec_${p}_${c}.json bundle_${p}_dec.json scores_dec27_${p}_${c}_internjudge.json intern >> $LOG 2>&1; echo "  internjudge ${p}_${c}">>$LOG
done; done

nuke; rm -f "$LOCK"
echo "=== M27 DECOUPLE-V2 DONE $(date) ===" >> $LOG
