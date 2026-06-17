"""起 vLLM 同时 serve 基座 + LoRA adapter(model=dep 走 adapter,基座名走基座)。
一个 server 即可对比 base vs FT。SFTP serve 脚本 + setsid 脱离 + 轮询。"""

import sys
import time

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

ADAPTER = "<REMOTE_WORKDIR>/ft/qwen14b-dep-lora"
SERVE_SH = f"""#!/bin/bash
cd <REMOTE_WORKDIR>
pkill -f 'vllm serve' 2>/dev/null
sleep 3
vllm serve <MODEL_DIR>/Qwen2.5-14B-Instruct \\
  --served-model-name Qwen/Qwen2.5-14B-Instruct \\
  --enable-lora --lora-modules dep={ADAPTER} --max-lora-rank 16 \\
  --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.9 \\
  > <REMOTE_WORKDIR>/logs/vllm_lora.log 2>&1
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    sftp.open("<REMOTE_WORKDIR>/serve_lora.sh", "w").write(SERVE_SH)
    sftp.close()
    c.exec_command("chmod +x <REMOTE_WORKDIR>/serve_lora.sh && setsid nohup bash <REMOTE_WORKDIR>/serve_lora.sh >/dev/null 2>&1 &")
    print("vLLM(base+LoRA)启动中,轮询 /v1/models(应出现 dep)...")
    for i in range(50):
        time.sleep(15)
        _, out, _ = c.exec_command(
            "curl -s --max-time 5 http://localhost:8000/v1/models 2>/dev/null | head -c 400; echo; "
            "pgrep -f 'vllm serve' >/dev/null && echo ALIVE || echo DEAD; "
            "tail -2 <REMOTE_WORKDIR>/logs/vllm_lora.log")
        txt = out.read().decode("utf-8", "replace")
        if '"dep"' in txt or '"id":"dep"' in txt:
            print(f"[{i}] READY ✅(base+dep 都在)\n{txt[:300]}")
            c.close(); return
        if "DEAD" in txt and i > 2:
            print(f"[{i}] 进程退出:\n{txt[-700:]}"); c.close(); return
        print(f"[{i}] 加载中...")
    print("TIMEOUT"); c.close()


if __name__ == "__main__":
    main()
