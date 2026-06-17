"""M9 第二层分析:RAG 强度梯度下,CoT 增益(cot − plain)是否重新显著。
若 CoT 增益在弱/带噪 RAG 下浮出 → 真凶是"强 RAG 抹平难度";
若再弱也不显著 → 排除该变量,"只有 RAG 重要"更顽固。

用法:python scripts/analyze_gradient.py
"""

import json
import math
import sys
from pathlib import Path

from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")

R = Path(__file__).resolve().parent.parent / "results"


def overalls(name):
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    return [sum(c["score"] for c in run) / len(run) for run in d["runs"]]


def hard_overalls(name):
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    out = []
    for run in d["runs"]:
        hs = [c["score"] for c in run if c["difficulty"] == "hard"]
        if hs:
            out.append(sum(hs) / len(hs))
    return out


def mean(xs):
    return sum(xs) / len(xs)


def compare(a, b, fn=overalls):
    A, B = fn(a), fn(b)
    ma, mb = mean(A), mean(B)
    t, p = stats.ttest_ind(A, B, equal_var=False)
    return ma, mb, mb - ma, p, len(A), len(B)  # d = cot - plain(正=CoT 有益)


LEVELS = [
    ("(a) 完美卡片", "werkzeug_full_general", "werkzeug_pe_cot"),
    ("(b) 不完整卡片", "werkzeug_full_general_incomplete", "werkzeug_pe_cot_incomplete"),
    ("(c) 带噪声卡片", "werkzeug_full_general_noisy", "werkzeug_pe_cot_noisy"),
    ("(d) 仅原始代码", "werkzeug_baseline_general", "werkzeug_rawcot"),
]


def main():
    print("=" * 78)
    print("M9 第二层:RAG 强度梯度 —— CoT 增益(pe_cot - plain)随卡片退化的变化")
    print("=" * 78)
    print(f"{'RAG强度':14s} {'plain':>8s} {'+CoT':>8s} {'ΔCoT':>9s} {'p':>8s}  判定")
    for label, plain, cot in LEVELS:
        try:
            mp, mc, d, p, na, nb = compare(plain, cot)
        except FileNotFoundError as e:
            print(f"{label:14s}  缺文件: {e}")
            continue
        sig = "✅显著" if p < 0.05 else "❌噪声内"
        print(f"{label:14s} {mp:8.4f} {mc:8.4f} {d:+9.4f} {p:8.4f}  {sig}  (n={na}/{nb})")

    print("\n— 仅 hard 难度子集上的 CoT 增益 —")
    print(f"{'RAG强度':14s} {'plain':>8s} {'+CoT':>8s} {'ΔCoT':>9s} {'p':>8s}  判定")
    for label, plain, cot in LEVELS:
        try:
            mp, mc, d, p, na, nb = compare(plain, cot, fn=hard_overalls)
        except FileNotFoundError:
            print(f"{label:14s}  缺文件")
            continue
        sig = "✅显著" if p < 0.05 else "❌噪声内"
        print(f"{label:14s} {mp:8.4f} {mc:8.4f} {d:+9.4f} {p:8.4f}  {sig}  (n={na}/{nb})")


if __name__ == "__main__":
    main()
