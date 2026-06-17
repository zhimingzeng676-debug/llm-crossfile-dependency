"""探测远端 GPU 机器环境(M3-B 上机前,用 paramiko 驱动 —— 本机不能直连 ssh)。

凭证按全局 CLAUDE.md 规则:本机无法交互式 ssh,统一用 paramiko。
注意:凭据改为从环境变量读取(REMOTE_HOST / REMOTE_PORT / REMOTE_USER / REMOTE_PWD),不在文件内硬编码/提交。
"""

import os
import paramiko

HOST = os.environ.get("REMOTE_HOST", "<HOST>")
PORT = int(os.environ.get("REMOTE_PORT", "22"))
USER = os.environ.get("REMOTE_USER", "root")
PASSWORD = os.environ.get("REMOTE_PWD", "<PASSWORD>")

CMDS = [
    ("GPU", "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || nvidia-smi"),
    ("CUDA", "nvcc --version 2>/dev/null | tail -1 || echo 'no nvcc'"),
    ("OS", "cat /etc/os-release 2>/dev/null | head -2; uname -a"),
    ("Python", "which python python3; python3 --version 2>&1"),
    ("conda", "which conda && conda --version || echo 'no conda'"),
    ("pip/torch", "python3 -c 'import torch;print(\"torch\",torch.__version__,\"cuda\",torch.cuda.is_available())' 2>&1 | head -3 || echo 'no torch'"),
    ("vllm", "python3 -c 'import vllm;print(vllm.__version__)' 2>&1 | head -1 || echo 'no vllm'"),
    ("disk", "df -h / /root /data 2>/dev/null | grep -v Filesystem"),
    ("mem", "free -g | head -2"),
    ("hf_cache", "ls -la ~/.cache/huggingface 2>/dev/null | head -5 || echo 'no hf cache'"),
    ("net_hfmirror", "curl -sI --max-time 15 https://hf-mirror.com 2>&1 | head -1 || echo 'mirror unreachable'"),
]


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接 {USER}@{HOST}:{PORT} ...")
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("连接成功。\n")
    for label, cmd in CMDS:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
        out = stdout.read().decode("utf-8", "replace").strip()
        err = stderr.read().decode("utf-8", "replace").strip()
        print(f"=== {label} ===")
        if out:
            print(out)
        if err and "no " not in err.lower():
            print("[stderr]", err[:300])
        print()
    c.close()


if __name__ == "__main__":
    main()
