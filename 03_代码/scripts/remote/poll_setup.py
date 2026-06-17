"""轮询远端环境搭建进度:模型下载大小、vllm 安装状态、相关进程。"""

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

CHECK = r"""
echo "=== 运行中的相关进程 ==="
ps aux | grep -E "huggingface-cli|pip install vllm" | grep -v grep | awk '{print $2, $11, $12, $13}'
echo "=== 模型下载大小 ==="
du -sh <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct 2>/dev/null || echo "(尚无目录)"
echo "=== download.log 末尾 ==="
tail -3 <REMOTE_WORKDIR>/logs/download.log 2>/dev/null || echo "(无日志)"
echo "=== vllm_install.log 末尾 ==="
tail -3 <REMOTE_WORKDIR>/logs/vllm_install.log 2>/dev/null || echo "(无日志)"
echo "=== vllm 是否装好 ==="
python3 -c "import vllm;print('vllm', vllm.__version__)" 2>&1 | tail -1
"""


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    _, stdout, _ = c.exec_command(CHECK, timeout=120)
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(stdout.read().decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
