# -*- coding: utf-8 -*-
"""强模型验证 — 通过 OpenAI 兼容 API 在 bundle 上生成答案。
API key / base 一律从环境变量读取(LINGYA_API_KEY / LINGYA_BASE),绝不硬编码、绝不进 git。
用法:python api_gen.py <bundle.json> <out.json> <model> [temp] [conc]
"""
import os, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = os.environ.get("LINGYA_API_KEY")
BASE = os.environ.get("LINGYA_BASE", "https://api.lingyaai.cn/v1")
if not KEY:
    raise SystemExit("请先设置环境变量 LINGYA_API_KEY(不要写进代码/仓库)。")
URL = BASE.rstrip("/") + "/chat/completions"

def call(prompt, model, temp):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp, "max_tokens": 1024}).encode("utf-8")
    for a in range(5):
        try:
            req = urllib.request.Request(URL, data=body,
                  headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception as e:
            if a < 4: time.sleep(3 * (a + 1)); continue
            return f"(ERR {str(e)[:80]})"

def main():
    bundle = json.load(open(sys.argv[1], encoding="utf-8"))
    out, model = sys.argv[2], sys.argv[3]
    temp = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    conc = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        ans = list(ex.map(lambda b: call(b["gen_prompt"], model, temp), bundle))
    run = [{"id": b["id"], "difficulty": b.get("difficulty"), "category": b.get("category"), "answer": a}
           for b, a in zip(bundle, ans)]
    json.dump({"gen_model": model, "n_runs": 1, "runs": [run]}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    err = sum(1 for a in ans if a.startswith("(ERR"))
    print(f"DONE {model} -> {out} ({time.time()-t0:.0f}s, {len(ans)} ans, {err} err)")

if __name__ == "__main__":
    main()
