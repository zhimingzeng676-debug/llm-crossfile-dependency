"""远端并发跑:N 轮生成(temp>0)+ 逐答 LLM-judge 打分(temp=0)。纯标准库 + 线程并发。
vLLM 连续批处理,几十并发即可把 56*N 条几分钟跑完。只回传分数,不回传全文。

用法:python3 gen_multi.py <bundle.json> <out.json> <gen_model> <judge_model> <temp> <n_runs> [concurrency]
输出:{config, gen_model, temp, n_runs, runs:[[{id,difficulty,category,score,hit,total}...] ...]}
"""

import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "http://localhost:8000/v1/chat/completions"

JUDGE_TMPL = """你是代码依赖分析评测裁判,只负责判断"模型回答"是否答对了"标准答案要点"。
评分标准(务必遵守):
- 命中正确的文件名/符号名/依赖或继承关系即算答对,**不计较措辞、语言、格式**;
- 模型多列了正确的额外信息**不扣分**;
- 只有**遗漏了要点**或给出**矛盾/错误**信息才扣分;
- 对"列出多个"的问题,按命中要点的**比例**打分(命中数/要点总数)。

[问题] {question}

[标准答案要点 — 必须命中这些] {gold}
[补充说明 — 标准答案的完整描述] {notes}

[模型回答]
{answer}

只输出一行 JSON,不要任何额外文字:
{{"hit": <命中要点数,整数>, "total": <要点总数,整数>, "score": <hit/total,0到1小数>, "reason": "<20字内理由>"}}"""


def call(prompt, model, temp, max_tokens, timeout=120):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    for attempt in range(5):
        try:
            req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 4:
                time.sleep(2 * (attempt + 1))
                continue
            return f"(ERR {e})"


def parse_score(txt):
    m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', txt)
    s = float(m.group(1)) if m else 0.0
    return max(0.0, min(1.0, s))


def main():
    bundle_path, out_path = sys.argv[1], sys.argv[2]
    gen_model, judge_model = sys.argv[3], sys.argv[4]
    temp = float(sys.argv[5])
    n_runs = int(sys.argv[6])
    conc = int(sys.argv[7]) if len(sys.argv) > 7 else 24

    bundle = json.load(open(bundle_path, encoding="utf-8"))
    runs = []
    t0 = time.time()
    for r in range(n_runs):
        # 1) 并发生成
        def gen_one(b):
            return call(b["gen_prompt"], gen_model, temp, 1024)
        with ThreadPoolExecutor(max_workers=conc) as ex:
            answers = list(ex.map(gen_one, bundle))
        # 2) 并发打分(temp=0,确定性,把方差全部归到生成侧)
        def judge_one(args):
            b, ans = args
            jp = JUDGE_TMPL.format(question=b["question"], gold=b["gold"],
                                   notes=b["notes"], answer=ans)
            return parse_score(call(jp, judge_model, 0.0, 256))
        with ThreadPoolExecutor(max_workers=conc) as ex:
            scores = list(ex.map(judge_one, zip(bundle, answers)))
        run = [{"id": b["id"], "difficulty": b["difficulty"], "category": b["category"],
                "score": sc} for b, sc in zip(bundle, scores)]
        runs.append(run)
        ov = sum(sc for sc in scores) / len(scores)
        print(f"  run {r + 1}/{n_runs} overall={ov:.4f} ({time.time() - t0:.0f}s)", flush=True)

    json.dump({"gen_model": gen_model, "judge_model": judge_model, "temp": temp,
               "n_runs": n_runs, "runs": runs},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE {n_runs} runs -> {out_path} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
