"""上传微调数据+训练脚本到远端,确认依赖,后台启动 QLoRA 训练。"""

import time
from pathlib import Path

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

PROJ = Path(__file__).resolve().parent.parent.parent


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    c.exec_command("mkdir -p <REMOTE_WORKDIR>/ft"); time.sleep(1)

    sftp = c.open_sftp()
    sftp.put(str(PROJ / "data" / "finetune_train.jsonl"), "<REMOTE_WORKDIR>/ft/finetune_train.jsonl")
    sftp.put(str(PROJ / "data" / "finetune_val.jsonl"), "<REMOTE_WORKDIR>/ft/finetune_val.jsonl")
    sftp.put(str(Path(__file__).parent / "train_qlora.py"), "<REMOTE_WORKDIR>/ft/train_qlora.py")
    sftp.close()
    print("已上传 train/val 数据 + train_qlora.py")

    # 确认依赖装好
    _, out, _ = c.exec_command("python3 -c 'import peft,bitsandbytes,datasets,accelerate; print(\"deps ok\")' 2>&1 | tail -2")
    print("依赖检查:", out.read().decode("utf-8", "replace").strip())

    # 后台启动训练(setsid 脱离)
    c.exec_command("cd <REMOTE_WORKDIR>/ft && setsid nohup python3 train_qlora.py > <REMOTE_WORKDIR>/logs/train.log 2>&1 &")
    print("训练已后台启动 -> <REMOTE_WORKDIR>/logs/train.log")
    c.close()


if __name__ == "__main__":
    main()
