"""M9 第一层分析:从 multi_<name>.json(N轮生成×逐答打分)算 均值+95%CI,
并对关键配置对做 Welch t 检验,判定"噪声内增益"是否真的显著。

用法:python scripts/analyze_multi.py
"""

import json
import math
import sys
from pathlib import Path

from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")

R = Path(__file__).resolve().parent.parent / "results"


def per_run_overall(name):
    """返回 (overall列表, 按难度的overall字典列表)。"""
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    overalls, by_diff_runs = [], []
    for run in d["runs"]:
        scs = [c["score"] for c in run]
        overalls.append(sum(scs) / len(scs))
        bd = {}
        for c in run:
            bd.setdefault(c["difficulty"], []).append(c["score"])
        by_diff_runs.append({k: sum(v) / len(v) for k, v in bd.items()})
    return overalls, by_diff_runs, d.get("n_runs")


def ci95(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = statistics_std(xs)
    se = sd / math.sqrt(n)
    h = stats.t.ppf(0.975, n - 1) * se if n > 1 else 0.0
    return m, sd, m - h, m + h


def statistics_std(xs):
    n = len(xs)
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0


def report(name, label):
    ov, bd, n = per_run_overall(name)
    m, sd, lo, hi = ci95(ov)
    print(f"\n[{label}]  {name}  (n={n} runs)")
    print(f"  overall = {m:.4f}  σ={sd:.4f}  95%CI=[{lo:.4f}, {hi:.4f}]")
    diffs = {}
    for k in ["easy", "medium", "hard"]:
        vals = [r[k] for r in bd if k in r]
        if vals:
            mm, _, l2, h2 = ci95(vals)
            print(f"    {k:7s} = {mm:.4f}  95%CI=[{l2:.4f}, {h2:.4f}]")
            diffs[k] = vals
    return ov, diffs


def _per_case_mean(name):
    """每题跨 N run 平均 → {id: 分}。15 次重跑仅用于降噪,不作样本量。"""
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    acc = {}
    for run in d["runs"]:
        for c in run:
            acc.setdefault(c["id"], []).append(c["score"])
    return {k: sum(v) / len(v) for k, v in acc.items()}


def compare(name_a, name_b, label_a, label_b):
    # 【2026-06-15 修复:指控二】正确统计单位 = 56 用例配对 t 检验(ttest_rel),
    # n=用例数(df=55),不是 15 次重跑。两条件共享同一套题 → 必须配对。
    # 旧版用 ttest_ind 对 15 个 run 均值检验 = 伪重复,制造 p≈1e-30 假精度,已废弃。
    a, b = _per_case_mean(name_a), _per_case_mean(name_b)
    ids = sorted(set(a) & set(b))
    da = [a[i] - b[i] for i in ids]
    n = len(ids)
    md = sum(da) / n
    sd = math.sqrt(sum((x - md) ** 2 for x in da) / (n - 1))
    se = sd / math.sqrt(n)
    t, p = stats.ttest_rel([a[i] for i in ids], [b[i] for i in ids])
    h = stats.t.ppf(0.975, n - 1) * se
    sig = "✅显著" if p < 0.05 else "❌不显著(噪声内)"
    print(f"\n>>> {label_a} - {label_b}: delta={md:+.4f}  95%CI=[{md-h:+.4f}, {md+h:+.4f}]  n={n}用例配对  p={p:.4f}  {sig}")


def main():
    print("=" * 70)
    print("M9 第一层:统计压方差(15-20轮重跑,固定判分确定性,95%CI)")
    print("=" * 70)
    report("werkzeug_full_general", "RAG only(plain)")
    report("werkzeug_pe_cot", "PE+RAG(System+CoT)")
    report("cell_all", "All(PE+RAG+FT)")
    report("werkzeug_pe_system", "PE(System only)")
    report("werkzeug_pe_domain", "PE+RAG+领域few-shot")

    print("\n" + "=" * 70)
    print("关键对比(Welch t,判定是否真信号)")
    print("=" * 70)
    compare("werkzeug_pe_cot", "werkzeug_full_general", "PE+RAG", "RAG only")
    compare("cell_all", "werkzeug_pe_cot", "All(+FT)", "PE+RAG")
    compare("werkzeug_pe_system", "werkzeug_full_general", "PE(System)", "RAG only")
    compare("werkzeug_pe_domain", "werkzeug_pe_cot", "+领域few-shot", "PE+RAG(无few-shot)")


if __name__ == "__main__":
    main()
