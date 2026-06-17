"""后台下载 E19 对照用的通用模型 Qwen2.5-14B-Instruct(与 Coder 同尺寸同家族,
隔离'代码专精 vs 通用'变量)。SFTP 上传下载脚本 + 后台启动。"""

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

DL = '''import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from huggingface_hub import snapshot_download
p = snapshot_download("Qwen/Qwen2.5-14B-Instruct",
    local_dir="<MODEL_DIR>/Qwen2.5-14B-Instruct", max_workers=8)
print("DONE", p)
'''


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    c.exec_command("pkill -f dl_general.py 2>/dev/null")
    sftp = c.open_sftp()
    sftp.open("<REMOTE_WORKDIR>/dl_general.py", "w").write(DL)
    sftp.close()
    c.exec_command("cd <REMOTE_WORKDIR> && setsid nohup python3 dl_general.py > logs/download_general.log 2>&1 &")
    print("通用模型 Qwen2.5-14B-Instruct 下载已后台启动。")
    c.close()


if __name__ == "__main__":
    main()
