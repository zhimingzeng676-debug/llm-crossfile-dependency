"""M12 任务二:自评估对照。两维度——准确率 + 幻觉/自信错误率。
abstained=模型说"信息不足";confident_wrong=未abstain且score<0.5(自信地答错=幻觉)。

用法:python scripts/analyze_selfassess.py
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"


def load(name):
    p = R / f"selfassess_{name}.json"
    if not p.exists():
        return None
    return json.load(open(p, encoding="utf-8"))["runs"]


def metrics(runs, filt=None):
    accs, abst, cw = [], [], []
    for run in runs:
        cs = [c for c in run if (filt is None or filt(c))]
        if not cs:
            continue
        accs.append(sum(c["score"] for c in cs) / len(cs))
        abst.append(sum(1 for c in cs if c["abstained"]) / len(cs))
        cw.append(sum(1 for c in cs if (not c["abstained"] and c["score"] < 0.5)) / len(cs))
    return (sum(accs) / len(accs), sum(abst) / len(abst), sum(cw) / len(cw)) if accs else (float("nan"),) * 3


CONFIGS = [
    ("无RAG · plain(纯瞎猜基线)", "baseline"),
    ("无RAG · 普通CoT", "pe_only"),
    ("无RAG · 自评估", "sa_norag"),
    ("深RAG · 自评估", "sa_deep"),
]


def main():
    print("=" * 78)
    print("M12 任务二:自评估 —— 准确率 vs 幻觉(自信错误)率,n=15")
    print("=" * 78)
    print(f"{'配置':28s} {'准确率':>8s} {'abstain率':>9s} {'自信错误率':>10s}")
    for label, name in CONFIGS:
        runs = load(name)
        if not runs:
            print(f"{label:28s}  (pending)")
            continue
        acc, ab, cw = metrics(runs)
        print(f"{label:28s} {acc:8.3f} {ab:9.3f} {cw:10.3f}")

    print("\n— 仅 hard 子集 —")
    for label, name in CONFIGS:
        runs = load(name)
        if not runs:
            continue
        acc, ab, cw = metrics(runs, lambda c: c["difficulty"] == "hard")
        print(f"{label:28s} acc={acc:.3f} abstain={ab:.3f} 自信错误={cw:.3f}")

    print("\n说明:核心看'无RAG'条件——上下文不足时,自评估应把'自信错误(幻觉)'转成'诚实abstain';")
    print("'深RAG'条件看自评估是否过度abstain伤准确率(对比 pe_cot_deep 准确率)。")


if __name__ == "__main__":
    main()
