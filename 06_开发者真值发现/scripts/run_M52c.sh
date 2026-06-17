#!/bin/bash
cd <REMOTE_WORKDIR>/task3
LOG=<REMOTE_WORKDIR>/task3/run_M52c.log
echo "=== M52C START $(date) ===" > $LOG
nuke(){ nvidia-smi --query-compute-apps=pid --format=csv,noheader|xargs -r kill -9 2>/dev/null; pkill -9 -i -f vllm 2>/dev/null; pkill -9 -f EngineCore 2>/dev/null; sleep 6; }
wait_ready(){ for i in $(seq 1 40); do curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null|grep -q "$1" && { echo "READY $1 ($i)">>$LOG; return 0; }; sleep 12; done; echo "TIMEOUT $1">>$LOG; return 1; }
serve(){ nuke; setsid bash -c "vllm serve $1 --served-model-name $2 --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.88 $3 > <REMOTE_WORKDIR>/task3/vllm_$2.log 2>&1" </dev/null >/dev/null 2>&1 & wait_ready $2; }

serve <MODEL_DIR>/internlm2_5-7b-chat internlm "--trust-remote-code" && {
  echo "=== xmodel internlm $(date) ===">>$LOG
  /usr/bin/python3.10 task3_score.py instances_mech.json scores_xmodel_internlm.json internlm no_card,static_card >>$LOG 2>&1; }
serve <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct coder && {
  echo "=== falsefriends full coder $(date) ===">>$LOG
  rm -f scores_ctrl_falsefriends.json scores_ctrl_falsefriends.json.log
  /usr/bin/python3.10 task3_score.py instances_ctrl_falsefriends.json scores_ctrl_falsefriends.json coder no_card,static_card >>$LOG 2>&1; }
nuke
echo "=== M52C DONE $(date) ===">>$LOG
nvidia-smi --query-gpu=memory.used --format=csv,noheader>>$LOG
