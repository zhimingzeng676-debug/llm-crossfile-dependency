"""M9 通用驱动:上传一个远端脚本 + 一个 bundle,跑,下载输出文件。

用法:python run_remote.py <script.py> <bundle_name> <out_name> [arg1 arg2 ...]
  bundle: results/bundle_<bundle_name>.json  -> 远端 bundle_<bundle_name>.json
  脚本被调用为: python3 <script> bundle_<bundle_name>.json <out_name> <arg...>
  下载 <out_name> -> results/<out_name>
"""

import sys
from pathlib import Path

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

PROJ = Path(__file__).resolve().parent.parent.parent
RESULTS = PROJ / "results"
REMOTE_DIR = "<REMOTE_WORKDIR>/gen"


def main():
    script = sys.argv[1]
    bundle_name = sys.argv[2]
    out_name = sys.argv[3]
    extra = sys.argv[4:]
    bundle_file = f"bundle_{bundle_name}.json"

    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    c.exec_command(f"mkdir -p {REMOTE_DIR}")
    import time
    time.sleep(1)
    sftp = c.open_sftp()
    sftp.put(str(RESULTS / bundle_file), f"{REMOTE_DIR}/{bundle_file}")
    sftp.put(str(Path(__file__).parent / script), f"{REMOTE_DIR}/{script}")
    print(f"已上传 {bundle_file} + {script}; 跑 {' '.join(extra)}")

    cmd = f"cd {REMOTE_DIR} && python3 {script} {bundle_file} {out_name} {' '.join(extra)}"
    chan = c.get_transport().open_session()
    chan.settimeout(3600)
    chan.exec_command(cmd)
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
    sftp.get(f"{REMOTE_DIR}/{out_name}", str(RESULTS / out_name))
    print(f"已下载 -> results/{out_name}")
    sftp.close()
    c.close()


if __name__ == "__main__":
    main()
