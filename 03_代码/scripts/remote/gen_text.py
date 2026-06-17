"""M15:只生成答案文本(不判分),供之后用统一的 base 裁判判分。并发,N 轮。
用法:python3 gen_text.py <bundle.json> <out.json> <gen_model> <temp> <n_runs> [conc]
输出 {runs:[[{id,difficulty,answer}...]...]}
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
URL = "http://localhost:8000/v1/chat/completions"

def call(prompt, model, temp):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp, "max_tokens": 1024}).encode("utf-8")
    for a in range(5):
        try:
            req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception as e:
            if a < 4: time.sleep(2*(a+1)); continue
            return f"(ERR {e})"

def main():
    bundle = json.load(open(sys.argv[1], encoding="utf-8"))
    out, gen, temp, n = sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5])
    conc = int(sys.argv[6]) if len(sys.argv) > 6 else 24
    runs = []; t0 = time.time()
    for r in range(n):
        with ThreadPoolExecutor(max_workers=conc) as ex:
            ans = list(ex.map(lambda b: call(b["gen_prompt"], gen, temp), bundle))
        runs.append([{"id": b["id"], "difficulty": b["difficulty"], "category": b["category"], "answer": a}
                     for b, a in zip(bundle, ans)])
        print(f"  gen run {r+1}/{n} ({time.time()-t0:.0f}s)", flush=True)
    json.dump({"gen_model": gen, "n_runs": n, "runs": runs}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE gen -> {out}")

if __name__ == "__main__": main()
