"""后台轮询通用模型 Qwen2.5-14B-Instruct 下载,完成(DONE + 无 incomplete)即退出。"""

import time

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

CHECK = (
    "D=$(grep -c DONE <REMOTE_WORKDIR>/logs/download_general.log 2>/dev/null || echo 0); "
    "I=$(find <MODEL_DIR>/Qwen2.5-14B-Instruct -name '*.incomplete' 2>/dev/null | wc -l); "
    "S=$(ls <MODEL_DIR>/Qwen2.5-14B-Instruct/*.safetensors 2>/dev/null | wc -l); "
    "echo \"DONE=$D INC=$I SAFE=$S\""
)


def poll():
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
        _, out, _ = c.exec_command(CHECK, timeout=60)
        line = out.read().decode("utf-8", "replace").strip()
        c.close()
        return line
    except Exception as e:
        return f"ERR={type(e).__name__}"


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for i in range(90):
        line = [l for l in poll().splitlines() if "DONE=" in l]
        line = line[-1] if line else ""
        kv = dict(p.split("=", 1) for p in line.split() if "=" in p)
        done = kv.get("DONE", "0") != "0"
        inc = kv.get("INC", "9")
        safe = kv.get("SAFE", "0")
        print(f"[{i:02d}] DONE={done} incomplete={inc} safetensors={safe}", flush=True)
        if done and inc == "0":
            print("READY: 通用模型下载完成。", flush=True)
            return
        time.sleep(60)
    print("TIMEOUT", flush=True)


if __name__ == "__main__":
    main()
