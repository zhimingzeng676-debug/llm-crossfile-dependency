"""在远端起 vLLM OpenAI server(SFTP 上传 serve.sh + setsid 彻底脱离,再轮询)。

用法:python start_vllm.py [模型目录] [served-name]
"""

import sys
import time

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

MODEL_DIR = sys.argv[1] if len(sys.argv) > 1 else "<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct"
SERVED_NAME = sys.argv[2] if len(sys.argv) > 2 else "Qwen/Qwen2.5-Coder-14B-Instruct"

SERVE_SH = f"""#!/bin/bash
cd <REMOTE_WORKDIR>
pkill -f 'vllm serve' 2>/dev/null
sleep 3
vllm serve {MODEL_DIR} \\
  --served-model-name {SERVED_NAME} \\
  --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.9 \\
  > <REMOTE_WORKDIR>/logs/vllm_serve.log 2>&1
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

    sftp = c.open_sftp()
    sftp.open("<REMOTE_WORKDIR>/serve.sh", "w").write(SERVE_SH)
    sftp.close()
    # setsid 彻底脱离会话,nohup 双保险
    c.exec_command("chmod +x <REMOTE_WORKDIR>/serve.sh && setsid nohup bash <REMOTE_WORKDIR>/serve.sh >/dev/null 2>&1 &")
    print(f"vLLM serve 已脱离启动(model={SERVED_NAME})。轮询 /v1/models ...")

    for i in range(50):  # ~12 分钟
        time.sleep(15)
        _, out, _ = c.exec_command(
            "P=$(pgrep -f 'vllm serve' | head -1); "
            "R=$(curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null | head -c 200); "
            "echo \"PROC=$P\"; echo \"RESP=$R\"; tail -3 <REMOTE_WORKDIR>/logs/vllm_serve.log 2>/dev/null"
        )
        txt = out.read().decode("utf-8", "replace")
        ready = '"id"' in txt or '"object"' in txt
        proc_alive = "PROC=" in txt and txt.split("PROC=")[1][0].isdigit()
        if ready:
            print(f"[{i}] vLLM READY ✅\n{txt[:250]}")
            c.close()
            return
        if not proc_alive and i > 2:
            print(f"[{i}] 进程已退出,日志尾:\n{txt[-800:]}")
            c.close()
            return
        print(f"[{i}] 加载中(proc_alive={proc_alive})... {txt.splitlines()[-1][:120] if txt.strip() else ''}")
    print("TIMEOUT:查 logs/vllm_serve.log")
    c.close()


if __name__ == "__main__":
    main()
