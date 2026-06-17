"""M14:从已 dump 的 prompts JSON 算检索质量 Recall@K / MRR(留出集 werkzeug)。
retrieved_sources(top-k 文件)对 expected_sources(标准答案文件)。无需 LLM。

用法:python scripts/compute_retrieval_metrics.py <name1> <name2> ...
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"


def metrics(name):
    d = json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))
    recs, mrrs = [], []
    by_diff = {}
    for p in d:
        retr = p["retrieved_sources"]
        exp = set(p["expected_sources"])
        if not exp:
            continue
        hit = exp & set(retr)
        rec = len(hit) / len(exp)
        # MRR:第一个命中 expected 的排名
        rr = 0.0
        for i, s in enumerate(retr, 1):
            if s in exp:
                rr = 1.0 / i
                break
        recs.append(rec); mrrs.append(rr)
        by_diff.setdefault(p.get("difficulty", "?"), []).append(rec)
    n = len(recs)
    return (sum(recs) / n, sum(mrrs) / n, n,
            {k: sum(v) / len(v) for k, v in by_diff.items()})


def main():
    print(f"{'配置':32s} {'Recall@K':>9s} {'MRR':>7s}  按难度Recall")
    for name in sys.argv[1:]:
        try:
            rec, mrr, n, bd = metrics(name)
        except FileNotFoundError:
            print(f"{name:32s}  缺 prompts 文件")
            continue
        bdstr = " ".join(f"{k}={v:.2f}" for k, v in sorted(bd.items()))
        print(f"{name:32s} {rec:9.4f} {mrr:7.4f}  {bdstr}")


if __name__ == "__main__":
    main()
