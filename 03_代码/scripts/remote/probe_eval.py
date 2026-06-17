"""M15:通用代码能力探针 pass@1(灾难性遗忘监控)。生成函数实现 -> 执行 assert 测试。
对一个 vLLM 上的模型测;DAPT 前后各跑一次,比 pass@1 是否下降。

用法(远端):python3 probe_eval.py <probe.jsonl> <model_name> <out.json>
"""

import json
import re
import subprocess
import sys
import urllib.request

URL = "http://localhost:8000/v1/chat/completions"


def call(prompt, model):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0, "max_tokens": 512}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def extract_code(text):
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    return m.group(1) if m else text


def run_test(code, test):
    prog = code + "\n" + test + "\nprint('PASS')\n"
    try:
        r = subprocess.run(["python3", "-c", prog], capture_output=True, text=True, timeout=10)
        return "PASS" in r.stdout
    except Exception:
        return False


def main():
    probe_path, model, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    probes = [json.loads(l) for l in open(probe_path, encoding="utf-8") if l.strip()]
    results = []
    npass = 0
    for p in probes:
        prompt = ("请补全下面的 Python 函数,只输出完整函数代码(可用 ```python 包裹),不要解释:\n\n" + p["prompt"])
        ans = call(prompt, model)
        code = extract_code(ans)
        ok = run_test(code, p["test"])
        npass += ok
        results.append({"id": p["id"], "pass": ok})
    pass1 = npass / len(probes)
    json.dump({"model": model, "pass@1": pass1, "n": len(probes), "results": results},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{model}: pass@1 = {pass1:.3f} ({npass}/{len(probes)}) -> {out_path}")


if __name__ == "__main__":
    main()
