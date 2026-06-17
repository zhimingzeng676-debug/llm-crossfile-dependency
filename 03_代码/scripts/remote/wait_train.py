"""后台轮询训练,完成(train_history.json 出现 或 train.log 有 DONE)即退出。
顺带打印最近的 train/val loss,便于过拟合监控。"""

import time

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

CHECK = (
    "D=$(test -f <REMOTE_WORKDIR>/ft/qwen14b-dep-lora/train_history.json && echo 1 || echo 0); "
    "L=$(grep -c 'DONE saved' <REMOTE_WORKDIR>/logs/train.log 2>/dev/null || echo 0); "
    "E=$(grep -iE 'Error|Traceback|CUDA out of memory' <REMOTE_WORKDIR>/logs/train.log 2>/dev/null | tail -1); "
    "P=$(grep -oE \"[0-9]+/93\" <REMOTE_WORKDIR>/logs/train.log | tail -1); "
    "echo \"DONE=$D L=$L PROG=$P ERR=${E:0:80}\""
)


def poll():
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
        _, o, _ = c.exec_command(CHECK, timeout=60)
        line = o.read().decode("utf-8", "replace").strip()
        c.close()
        return line
    except Exception as e:
        return f"ERRC={type(e).__name__}"


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for i in range(60):
        line = [l for l in poll().splitlines() if "DONE=" in l or "ERRC=" in l]
        line = line[-1] if line else ""
        print(f"[{i:02d}] {line}", flush=True)
        if "DONE=1" in line or "L=1" in line:
            print("READY: 训练完成。", flush=True)
            return
        time.sleep(60)
    print("TIMEOUT", flush=True)


if __name__ == "__main__":
    main()
