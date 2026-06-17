"""M11:相似度检索 vs 依赖检索 vs 融合 的对照分析。
读 multi_*.json(n=15),出 overall + 分难度 + 分类型(重点反向/间接)+ Welch t。

用法:python scripts/analyze_fusion.py
"""

import json
import math
import sys
from pathlib import Path

from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"

CONFIGS = [
    ("纯依赖卡片(5dep)", "werkzeug_dep_only"),
    ("纯相似度(5sim)", "werkzeug_sim_only"),
    ("融合 3dep+2sim", "werkzeug_fuse_3d2s"),
    ("融合 2dep+3sim", "werkzeug_fuse_2d3s"),
    ("当前默认混合(pe_cot)", "werkzeug_pe_cot"),
]


def runs(name):
    return json.load(open(R / f"multi_{name}.json", encoding="utf-8"))["runs"]


def overalls(name, filt=None):
    out = []
    for run in runs(name):
        xs = [c["score"] for c in run if (filt is None or filt(c))]
        if xs:
            out.append(sum(xs) / len(xs))
    return out


def m(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def ci(xs):
    n = len(xs)
    if n < 2:
        return m(xs), 0.0
    mm = m(xs)
    sd = math.sqrt(sum((x - mm) ** 2 for x in xs) / (n - 1))
    return mm, stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)


def cats(name):
    s = set()
    for c in runs(name)[0]:
        s.add(c["category"])
    return sorted(s)


def main():
    allcats = cats("werkzeug_pe_cot")
    print("=" * 90)
    print("M11 相似度检索 vs 依赖检索 vs 融合(werkzeug 56;n=15;95%CI;裁判 general temp=0)")
    print("=" * 90)
    print(f"{'配置':24s} {'overall':>14s} {'hard':>8s} | " + " ".join(f"{c[:10]:>11s}" for c in allcats))
    for label, name in CONFIGS:
        ov = overalls(name); mm, h = ci(ov)
        hd = m(overalls(name, lambda c: c["difficulty"] == "hard"))
        bycat = [m(overalls(name, lambda c, cc=cc: c["category"] == cc)) for cc in allcats]
        print(f"{label:24s} {mm:.4f}±{h:.4f} {hd:8.3f} | " + " ".join(f"{x:11.3f}" for x in bycat))

    print("\n— 关键对比(Welch t,vs 纯依赖卡片基准)—")
    base = overalls("werkzeug_dep_only")
    for label, name in CONFIGS:
        if name == "werkzeug_dep_only":
            continue
        x = overalls(name)
        t, p = stats.ttest_ind(x, base, equal_var=False)
        sig = "✅" if p < 0.05 else "❌噪声内"
        print(f"  {label:24s} − 纯依赖: Δ={m(x)-m(base):+.4f}  p={p:.4f}  {sig}")

    print("\n— 反向依赖 / 间接依赖 子集(相似度检索最该帮的地方)—")
    for cc in allcats:
        if "reverse" in cc or "indirect" in cc or "间接" in cc or "反向" in cc:
            print(f"  [{cc}]")
            b = overalls("werkzeug_dep_only", lambda c, x=cc: c["category"] == x)
            for label, name in CONFIGS:
                x = overalls(name, lambda c, xx=cc: c["category"] == xx)
                if not x:
                    continue
                tag = ""
                if name != "werkzeug_dep_only" and b:
                    t, p = stats.ttest_ind(x, b, equal_var=False)
                    tag = f"  Δvs依赖={m(x)-m(b):+.3f} p={p:.3f}"
                print(f"     {label:24s} {m(x):.3f}{tag}")


if __name__ == "__main__":
    main()
