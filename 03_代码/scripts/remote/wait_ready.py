"""后台轮询远端,直到 (模型下载完成 AND vLLM 可导入) 才退出。退出即通知。"""

import time

import paramiko

from probe_gpu import HOST, PASSWORD, PORT, USER

CHECK = r"""
DL=$(grep -c "DONE <MODEL_DIR>" <REMOTE_WORKDIR>/logs/download.log 2>/dev/null || echo 0)
SZ=$(du -sb <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct 2>/dev/null | awk '{print $1}')
VL=$(python3 -c "import vllm" 2>/dev/null && echo OK || echo NO)
echo "DL=$DL SZ=${SZ:-0} VL=$VL"
"""


def poll():
    """连一次远端跑 CHECK;任何连接/执行异常都吞掉返回 ''(下次再试),不让轮询挂掉。"""
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
    for i in range(120):  # 最多 ~120 分钟
        line = poll()
        # 只取最后一行、只解析含 = 的 token(远端可能混入告警行)
        last = [l for l in line.splitlines() if "=" in l]
        line = last[-1] if last else ""
        kv = dict(p.split("=", 1) for p in line.split() if "=" in p)
        dl_done = kv.get("DL", "0") != "0"
        sz_gb = int(kv.get("SZ", "0")) / 1e9
        vllm_ok = kv.get("VL") == "OK"
        print(f"[{i:02d}] 下载完成={dl_done} 模型大小={sz_gb:.1f}G vllm={vllm_ok}", flush=True)
        if (dl_done or sz_gb > 27) and vllm_ok:
            print("READY: 模型与 vLLM 都就绪。", flush=True)
            return
        time.sleep(60)
    print("TIMEOUT: 超时未就绪,手动查 poll_setup.py", flush=True)


if __name__ == "__main__":
    main()
