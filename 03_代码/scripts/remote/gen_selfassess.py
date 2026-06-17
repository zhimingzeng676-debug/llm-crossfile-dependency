"""M12 自评估对照:并发生成 + 判分 + 标记"是否 abstain(说信息不足)"。
返回每例 {score, abstained, difficulty, category},用于算 准确率 + abstain率 + 自信错误率。

用法:python3 gen_selfassess.py <bundle.json> <out.json> <gen_model> <judge_model> <temp> <n_runs> [conc]
"""

import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "http://localhost:8000/v1/chat/completions"

JUDGE_TMPL = """你是代码依赖分析评测裁判,只负责判断"模型回答"是否答对了"标准答案要点"。
- 命中正确的文件名/符号名/依赖或继承关系即算答对,不计较措辞;多列正确不扣分;遗漏或矛盾才扣分;
- "列出多个"按命中比例打分。
- 注意:若模型回答是"信息不足"之类的拒答,说明它没有给出要点,按未命中处理(score 接近 0)。
[问题] {question}
[标准答案要点] {gold}
[补充说明] {notes}
[模型回答]
{answer}
只输出一行 JSON:{{"hit":<int>,"total":<int>,"score":<0-1小数>}}"""

# abstain 检测:模型明确表示信息不足/无法确定/未包含,而非给出实质依赖答案
ABSTAIN_PAT = re.compile(r"信息不足|提供的信息中未包含|无法确定|上下文.{0,6}不足|没有.{0,4}(足够|相关).{0,6}(信息|上下文|卡片)")


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


def pscore(t):
    m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', t)
    return max(0.0, min(1.0, float(m.group(1)))) if m else 0.0


def main():
    bundle_path, out_path = sys.argv[1], sys.argv[2]
    gen_model, judge_model = sys.argv[3], sys.argv[4]
    temp = float(sys.argv[5]); n_runs = int(sys.argv[6])
    conc = int(sys.argv[7]) if len(sys.argv) > 7 else 24
    bundle = json.load(open(bundle_path, encoding="utf-8"))
    runs = []
    t0 = time.time()
    for r in range(n_runs):
        with ThreadPoolExecutor(max_workers=conc) as ex:
            answers = list(ex.map(lambda b: call(b["gen_prompt"], gen_model, temp, 1024), bundle))

        def judge(args):
            b, ans = args
            ab = bool(ABSTAIN_PAT.search(ans))
            jp = JUDGE_TMPL.format(question=b["question"], gold=b["gold"], notes=b["notes"], answer=ans)
            sc = pscore(call(jp, judge_model, 0.0, 200))
            return {"id": b["id"], "difficulty": b["difficulty"], "category": b["category"],
                    "score": sc, "abstained": ab}
        with ThreadPoolExecutor(max_workers=conc) as ex:
            run = list(ex.map(judge, zip(bundle, answers)))
        runs.append(run)
        acc = sum(x["score"] for x in run) / len(run)
        ab = sum(1 for x in run if x["abstained"]) / len(run)
        print(f"  run {r+1}/{n_runs} acc={acc:.4f} abstain={ab:.3f} ({time.time()-t0:.0f}s)", flush=True)
    json.dump({"gen_model": gen_model, "n_runs": n_runs, "runs": runs},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE -> {out_path} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
