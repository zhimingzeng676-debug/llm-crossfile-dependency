"""上传 M38-40 大样本脏依赖 5 条件 bundle + gen/judge 脚本到远端,启动 eval_M38.sh(后台)。"""
import os, paramiko, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent.parent
# 凭据从环境变量读取,不硬编码/提交(REMOTE_HOST / REMOTE_PORT / REMOTE_USER / REMOTE_PWD)
HOST, PORT, USER, PWD = (os.environ.get("REMOTE_HOST", "<HOST>"), int(os.environ.get("REMOTE_PORT", "22")),
                         os.environ.get("REMOTE_USER", "root"), os.environ.get("REMOTE_PWD", "<PASSWORD>"))
RDIR = "<REMOTE_WORKDIR>/phaseM"

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30)
def run(cmd):
    i, o, e = c.exec_command(cmd); out = o.read().decode(); err = e.read().decode()
    return out, err
run(f"mkdir -p {RDIR} <REMOTE_WORKDIR>/logs")
sftp = c.open_sftp()
# bundles
for name in ["strict", "humble", "baseline", "humble_source", "humble_prompt"]:
    sftp.put(str(ROOT/"results"/"dirty_large"/f"bundle_{name}.json"), f"{RDIR}/bundle_{name}.json")
# scripts
for s in ["gen_text.py", "judge_text.py"]:
    sftp.put(str(ROOT/"scripts"/"remote"/s), f"{RDIR}/{s}")
sftp.put(str(ROOT/"scripts"/"remote"/"eval_M38.sh"), "<REMOTE_WORKDIR>/eval_M38.sh")
sftp.close()
print("上传完成:5 bundle + gen/judge + eval_M38.sh")
# 启动(后台 detached)
run("rm -f <REMOTE_WORKDIR>/eval_M38.lock")
run("chmod +x <REMOTE_WORKDIR>/eval_M38.sh; setsid bash <REMOTE_WORKDIR>/eval_M38.sh ><REMOTE_WORKDIR>/logs/M38_boot.log 2>&1 < /dev/null &")
print("已后台启动 eval_M38.sh")
out, _ = run("sleep 3; tail -3 <REMOTE_WORKDIR>/logs/eval_M38.log 2>/dev/null; nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print(out)
c.close()
