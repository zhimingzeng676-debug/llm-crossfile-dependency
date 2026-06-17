"""M15:用统一 base 裁判给已生成的答案文本判分(消除 self-judge 不一致)。
用法:python3 judge_text.py <answers.json> <bundle.json> <out.json> <judge_model> [conc]
输出 {runs:[[{id,difficulty,category,score}...]...]}(可被 analyze 直接读)
"""
import json, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
URL = "http://localhost:8000/v1/chat/completions"
JT = """你是代码依赖分析评测裁判,只判断"模型回答"是否答对了"标准答案要点"。
- 命中正确文件/符号/依赖或继承关系即算对,不计较措辞;多列正确不扣分;遗漏或矛盾才扣分;
- "列出多个"按命中比例打分。
[问题] {q}
[标准答案要点] {gold}
[补充说明] {notes}
[模型回答]
{ans}
只输出一行 JSON:{{"hit":<int>,"total":<int>,"score":<0-1小数>}}"""

def call(p, m):
    body = json.dumps({"model": m, "messages": [{"role": "user", "content": p}], "temperature": 0.0, "max_tokens": 200}).encode("utf-8")
    for a in range(5):
        try:
            req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception as e:
            if a < 4: time.sleep(2*(a+1)); continue
            return "{}"

def ps(t):
    m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', t); return max(0.0, min(1.0, float(m.group(1)))) if m else 0.0

def main():
    ans = json.load(open(sys.argv[1], encoding="utf-8"))["runs"]
    bundle = {b["id"]: b for b in json.load(open(sys.argv[2], encoding="utf-8"))}
    out, judge = sys.argv[3], sys.argv[4]
    conc = int(sys.argv[5]) if len(sys.argv) > 5 else 24
    runs = []; t0 = time.time()
    for ri, run in enumerate(ans):
        def j(c):
            b = bundle[c["id"]]
            p = JT.format(q=b["question"], gold=b["gold"], notes=b["notes"], ans=c["answer"])
            return {"id": c["id"], "difficulty": c["difficulty"], "category": c.get("category", "?"), "score": ps(call(p, judge))}
        with ThreadPoolExecutor(max_workers=conc) as ex:
            runs.append(list(ex.map(j, run)))
        ov = sum(x["score"] for x in runs[-1]) / len(runs[-1])
        print(f"  judge run {ri+1}/{len(ans)} overall={ov:.4f} ({time.time()-t0:.0f}s)", flush=True)
    json.dump({"judge_model": judge, "n_runs": len(runs), "runs": runs}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE judge -> {out}")

if __name__ == "__main__": main()
