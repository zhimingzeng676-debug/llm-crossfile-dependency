"""驱动:上传 prompts JSON + gen_answers.py 到远端,远端跑生成,下载 answers JSON。

用法:python run_remote_gen.py <prompts_文件名> <model_name>
  prompts 文件在本机 results/ 下,answers 写回本机 results/answers_<同名>。
"""

import sys
from pathlib import Path

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

PROJ = Path(__file__).resolve().parent.parent.parent  # D:\claude\49
RESULTS = PROJ / "results"
REMOTE_DIR = "<REMOTE_WORKDIR>/gen"


def main():
    prompts_name = sys.argv[1]               # 如 prompts_werkzeug_graphcards_qwen.json
    model = sys.argv[2]
    temp = sys.argv[3] if len(sys.argv) > 3 else "0.0"
    out_suffix = sys.argv[4] if len(sys.argv) > 4 else ""  # 多次重跑用不同后缀
    answers_name = prompts_name.replace("prompts_", "answers_")
    if out_suffix:
        answers_name = answers_name.replace(".json", f"_{out_suffix}.json")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    c.exec_command(f"mkdir -p {REMOTE_DIR}")
    import time
    time.sleep(1)

    sftp = c.open_sftp()
    sftp.put(str(RESULTS / prompts_name), f"{REMOTE_DIR}/{prompts_name}")
    sftp.put(str(Path(__file__).parent / "gen_answers.py"), f"{REMOTE_DIR}/gen_answers.py")
    print(f"已上传 {prompts_name} + gen_answers.py")

    # 前台跑生成(阻塞直到完成),实时读 stdout
    cmd = (f"cd {REMOTE_DIR} && python3 gen_answers.py {prompts_name} "
           f"{answers_name} '{model}' {temp}")
    chan = c.get_transport().open_session()
    chan.settimeout(1800)
    chan.exec_command(cmd)
    sys.stdout.reconfigure(encoding="utf-8")
    buf = b""
    while True:
        if chan.recv_ready():
            buf += chan.recv(8192)
            *lines, buf = buf.split(b"\n")
            for ln in lines:
                print("  [远端]", ln.decode("utf-8", "replace"))
        if chan.exit_status_ready() and not chan.recv_ready():
            break
    print(chan.recv_exit_status() and "[远端非0退出]" or "[远端完成]")

    sftp.get(f"{REMOTE_DIR}/{answers_name}", str(RESULTS / answers_name))
    print(f"已下载 -> results/{answers_name}")
    sftp.close()
    c.close()


if __name__ == "__main__":
    main()
