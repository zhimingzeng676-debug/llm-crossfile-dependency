"""远端 A800 环境搭建(后台启动 vLLM 安装 + Qwen2.5-Coder-14B 下载)。

用 paramiko 驱动;长任务用 nohup 后台跑 + 日志,channel 关了也不中断。
跑完返回,后续用 poll_setup.py 轮询日志。
"""

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

MODEL = "Qwen/Qwen2.5-Coder-14B-Instruct"

# 一次性把准备命令拼好。HF_ENDPOINT 走镜像;下载和装 vllm 各自后台 + 独立日志。
SETUP = r"""
set -e
mkdir -p <REMOTE_WORKDIR>/logs <MODEL_DIR>
cd <REMOTE_WORKDIR>
# pip 基础 + huggingface_hub(快)
python3 -m pip install -U pip -q 2>&1 | tail -2
python3 -m pip install -U "huggingface_hub[cli]" -q 2>&1 | tail -2
echo "pip+hf ready"
"""

# 后台:下模型(断点续传,走镜像),日志 download.log
DOWNLOAD = (
    "cd <REMOTE_WORKDIR> && "
    "HF_ENDPOINT=https://hf-mirror.com nohup huggingface-cli download "
    f"{MODEL} --local-dir <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct "
    "> <REMOTE_WORKDIR>/logs/download.log 2>&1 & echo \"download pid $!\""
)

# 后台:装 vllm(会带 torch+cuda wheel),日志 vllm_install.log
VLLM = (
    "cd <REMOTE_WORKDIR> && "
    "nohup python3 -m pip install vllm "
    "> <REMOTE_WORKDIR>/logs/vllm_install.log 2>&1 & echo \"vllm-install pid $!\""
)


def run(c, cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("连接成功,准备基础环境(pip + huggingface_hub)...")
    out, err = run(c, SETUP, timeout=600)
    print(out.strip())
    if "ready" not in out:
        print("[stderr]", err[-500:])

    print("\n后台启动模型下载 ...")
    out, _ = run(c, DOWNLOAD)
    print(out.strip())

    print("后台启动 vLLM 安装 ...")
    out, _ = run(c, VLLM)
    print(out.strip())

    print("\n两个后台任务已起。用 scripts/remote/poll_setup.py 轮询进度。")
    c.close()


if __name__ == "__main__":
    main()
