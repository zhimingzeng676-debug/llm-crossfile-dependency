"""M9 驱动:上传 bundle + gen_multi.py,远端并发跑 N 轮生成+打分,下载分数。

用法:python run_multi.py <bundle_name> <gen_model> <judge_model> <temp> <n_runs> [conc]
  bundle 文件在本机 results/bundle_<name>.json,结果写回 results/multi_<name>.json
"""

import sys
from pathlib import Path

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

PROJ = Path(__file__).resolve().parent.parent.parent
RESULTS = PROJ / "results"
REMOTE_DIR = "<REMOTE_WORKDIR>/gen"


def main():
    bundle_name = sys.argv[1]          # 如 werkzeug_pe_cot
    gen_model = sys.argv[2]
    judge_model = sys.argv[3]
    temp = sys.argv[4]
    n_runs = sys.argv[5]
    conc = sys.argv[6] if len(sys.argv) > 6 else "24"
    bundle_file = f"bundle_{bundle_name}.json"
    out_file = f"multi_{bundle_name}.json"

    sys.stdout.reconfigure(encoding="utf-8")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    c.exec_command(f"mkdir -p {REMOTE_DIR}")
    import time
    time.sleep(1)
    sftp = c.open_sftp()
    sftp.put(str(RESULTS / bundle_file), f"{REMOTE_DIR}/{bundle_file}")
    sftp.put(str(Path(__file__).parent / "gen_multi.py"), f"{REMOTE_DIR}/gen_multi.py")
    print(f"已上传 {bundle_file} + gen_multi.py,开始 {n_runs} 轮 (gen={gen_model}, judge={judge_model}, temp={temp})")

    cmd = (f"cd {REMOTE_DIR} && python3 gen_multi.py {bundle_file} {out_file} "
           f"'{gen_model}' '{judge_model}' {temp} {n_runs} {conc}")
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

    sftp.get(f"{REMOTE_DIR}/{out_file}", str(RESULTS / out_file))
    print(f"已下载 -> results/{out_file}")
    sftp.close()
    c.close()


if __name__ == "__main__":
    main()
