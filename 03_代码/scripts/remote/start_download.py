"""把模型下载脚本 SFTP 上传到远端并后台启动(避开多层引号问题)。"""

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

DL_SCRIPT = '''import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from huggingface_hub import snapshot_download
p = snapshot_download(
    "Qwen/Qwen2.5-Coder-14B-Instruct",
    local_dir="<MODEL_DIR>/Qwen2.5-Coder-14B-Instruct",
    max_workers=8,
)
print("DONE", p)
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    # 先清掉之前可能在跑的下载
    c.exec_command("pkill -f dl.py 2>/dev/null")
    sftp = c.open_sftp()
    sftp.open("<REMOTE_WORKDIR>/dl.py", "w").write(DL_SCRIPT)
    sftp.close()
    # 后台启动
    c.exec_command("cd <REMOTE_WORKDIR> && nohup python3 dl.py > logs/download.log 2>&1 &")
    print("下载脚本已上传并后台启动。")
    c.close()


if __name__ == "__main__":
    main()
