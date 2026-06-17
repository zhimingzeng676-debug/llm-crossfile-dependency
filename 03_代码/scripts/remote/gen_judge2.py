"""M9 第三层:同一批答案,用两套裁判打分,查"评测分辨率"是否吃掉了模型优化的增益。
裁判1 = 原比例式(hit/total,只看实体命中);裁判2 = 细粒度多维(实体+关系+推理/清晰,0-5)。
生成用 temp=0(确定性,排除生成方差),把差异全部归到"裁判粗细"上。

用法:python3 gen_judge2.py <bundle.json> <out.json> <gen_model> <judge_model> [n_runs] [conc]
输出:{runs:[[{id,difficulty,score1,score2}...] ...]}(score1/score2 同为0-1)
"""

import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "http://localhost:8000/v1/chat/completions"

J1 = """你是代码依赖分析评测裁判,只负责判断"模型回答"是否答对了"标准答案要点"。
- 命中正确的文件名/符号名/依赖或继承关系即算答对,不计较措辞、语言、格式;
- 多列正确信息不扣分;只有遗漏要点或矛盾才扣分;
- 对"列出多个"的问题,按命中比例打分(命中数/要点总数)。
[问题] {question}
[标准答案要点] {gold}
[补充说明] {notes}
[模型回答]
{answer}
只输出一行 JSON:{{"hit":<int>,"total":<int>,"score":<hit/total,0-1小数>}}"""

J2 = """你是代码依赖分析评测裁判。请对"模型回答"按 3 个维度细粒度打分(即使没完全答对也要给出部分分):
A. 实体命中——是否点到正确的文件/符号(0-2:全中2,部分1,无0)
B. 关系正确——依赖/继承/调用的方向与对象是否正确(0-2:完全对2,方向或部分错1,错0)
C. 推理与表述——多跳路径/中间文件/解释是否正确且清晰无矛盾(0-1:好1,差0)
总分 = A+B+C(0-5)。对"答案方向对、解释清楚但漏了个别实体"的回答,要体现出比"完全错"更高的分。
[问题] {question}
[标准答案要点] {gold}
[补充说明] {notes}
[模型回答]
{answer}
只输出一行 JSON:{{"A":<0-2>,"B":<0-2>,"C":<0-1>,"total":<A+B+C,0-5>}}"""


def call(prompt, model, temp, max_tokens, timeout=120):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": temp, "max_tokens": max_tokens}).encode("utf-8")
    for attempt in range(5):
        try:
            req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < 4:
                time.sleep(2 * (attempt + 1)); continue
            return f"(ERR {e})"


def num(txt, key, default=0.0):
    m = re.search(rf'"{key}"\s*:\s*([0-9]*\.?[0-9]+)', txt)
    return float(m.group(1)) if m else default


def main():
    bundle_path, out_path = sys.argv[1], sys.argv[2]
    gen_model, judge_model = sys.argv[3], sys.argv[4]
    n_runs = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    conc = int(sys.argv[6]) if len(sys.argv) > 6 else 24
    bundle = json.load(open(bundle_path, encoding="utf-8"))
    runs = []
    t0 = time.time()
    for r in range(n_runs):
        with ThreadPoolExecutor(max_workers=conc) as ex:
            answers = list(ex.map(lambda b: call(b["gen_prompt"], gen_model, 0.0, 1024), bundle))

        def judge(args):
            b, ans = args
            t1 = call(J1.format(question=b["question"], gold=b["gold"], notes=b["notes"], answer=ans), judge_model, 0.0, 200)
            t2 = call(J2.format(question=b["question"], gold=b["gold"], notes=b["notes"], answer=ans), judge_model, 0.0, 200)
            s1 = max(0.0, min(1.0, num(t1, "score")))
            s2 = max(0.0, min(1.0, num(t2, "total") / 5.0))
            return {"id": b["id"], "difficulty": b["difficulty"], "score1": s1, "score2": s2}
        with ThreadPoolExecutor(max_workers=conc) as ex:
            run = list(ex.map(judge, zip(bundle, answers)))
        runs.append(run)
        o1 = sum(x["score1"] for x in run) / len(run)
        o2 = sum(x["score2"] for x in run) / len(run)
        print(f"  run {r + 1}/{n_runs} judge1={o1:.4f} judge2={o2:.4f} ({time.time() - t0:.0f}s)", flush=True)
    json.dump({"gen_model": gen_model, "n_runs": n_runs, "runs": runs},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE -> {out_path} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
