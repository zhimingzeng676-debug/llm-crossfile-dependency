# -*- coding: utf-8 -*-
"""强模型验证 LLM-judge 辅口径(gen≠judge)。judge 模型经 API,key 从环境变量读取。
用法:python api_judge.py <answers.json> <bundle.json> <out.json> <judge_model> [conc]
"""
import os, re, sys, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = os.environ.get("LINGYA_API_KEY")
BASE = os.environ.get("LINGYA_BASE", "https://api.lingyaai.cn/v1")
if not KEY:
    raise SystemExit("请先设置环境变量 LINGYA_API_KEY。")
URL = BASE.rstrip("/") + "/chat/completions"
JT = """你是代码依赖分析阅卷助手,只判断"模型回答"是否满足"标准答案要求"。
- 命中正确文件/符号/依赖关系越多分越高;不正确扣分;漏列或矛盾扣分;
- "列出多个"的题需列表完整。
[问题] {q}
[标准答案要点] {gold}
[补充说明] {notes}
[模型回答]
{ans}
只输出一行 JSON:{{"score":<0到1小数>}}"""

def call(p, m):
    body = json.dumps({"model": m, "messages": [{"role": "user", "content": p}],
                       "temperature": 0.0, "max_tokens": 200}).encode("utf-8")
    for a in range(5):
        try:
            req = urllib.request.Request(URL, data=body,
                  headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception:
            if a < 4: time.sleep(3 * (a + 1)); continue
            return "{}"

def ps(t):
    m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', t)
    return max(0.0, min(1.0, float(m.group(1)))) if m else 0.0

def main():
    run = json.load(open(sys.argv[1], encoding="utf-8"))["runs"][0]
    bundle = {b["id"]: b for b in json.load(open(sys.argv[2], encoding="utf-8"))}
    out, judge = sys.argv[3], sys.argv[4]
    conc = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    def j(c):
        b = bundle[c["id"]]
        p = JT.format(q=b["question"], gold=b["gold"], notes=b.get("notes", ""), ans=c["answer"])
        return ps(call(p, judge))
    with ThreadPoolExecutor(max_workers=conc) as ex:
        sc = list(ex.map(j, run))
    json.dump({"judge": judge, "scores": sc, "mean": round(sum(sc) / len(sc), 4)},
              open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE judge={judge} {sys.argv[1]} -> mean={sum(sc)/len(sc):.4f}")

if __name__ == "__main__":
    main()
