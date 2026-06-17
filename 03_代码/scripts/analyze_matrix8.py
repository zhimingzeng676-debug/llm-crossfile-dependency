"""M10:完整 8 格消融矩阵(2^3 = {PE}×{RAG}×{FT})。读 8 个 multi_*.json,
统一口径(同模型族、同裁判 general temp=0、同 temp=0.7 生成、同 n),出 overall+难度+95%CI,
并算三手段的"边际效应"(固定另两者,单独开/关某手段的平均影响)。

用法:python scripts/analyze_matrix8.py
"""

import json
import math
import sys
from pathlib import Path

from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"

# (PE,RAG,FT) -> multi 文件名
CELLS = {
    (0, 0, 0): "cell_baseline",
    (1, 0, 0): "cell_pe_only",
    (0, 1, 0): "werkzeug_full_general",
    (0, 0, 1): "cell_ft_only",
    (1, 1, 0): "werkzeug_pe_cot",
    (1, 0, 1): "cell_pe_ft",
    (0, 1, 1): "cell_rag_ft",
    (1, 1, 1): "cell_all",
}
LABEL = {(0,0,0):"baseline(none)",(1,0,0):"PE only",(0,1,0):"RAG only",(0,0,1):"FT only",
         (1,1,0):"PE+RAG",(1,0,1):"PE+FT",(0,1,1):"RAG+FT",(1,1,1):"All(PE+RAG+FT)"}


def overalls(name):
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    return [sum(c["score"] for c in run) / len(run) for run in d["runs"]]


def by_diff(name, diff):
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    out = []
    for run in d["runs"]:
        xs = [c["score"] for c in run if c["difficulty"] == diff]
        if xs:
            out.append(sum(xs) / len(xs))
    return out


def m(xs):
    return sum(xs) / len(xs)


def ci(xs):
    n = len(xs); mm = m(xs)
    sd = math.sqrt(sum((x-mm)**2 for x in xs)/(n-1)) if n > 1 else 0
    h = stats.t.ppf(0.975, n-1)*sd/math.sqrt(n) if n > 1 else 0
    return mm, h


def main():
    data = {k: overalls(v) for k, v in CELLS.items()}
    print("=" * 76)
    print("M10 完整 8 格消融矩阵(werkzeug 56 用例;通用14B族;裁判 general temp=0;")
    print("生成 temp=0.7;每格 n=15;95%CI)")
    print("=" * 76)
    print(f"{'格 (PE,RAG,FT)':22s} {'overall':>14s} {'easy':>7s} {'medium':>7s} {'hard':>7s}  n")
    for k in [(0,0,0),(1,0,0),(0,1,0),(0,0,1),(1,1,0),(1,0,1),(0,1,1),(1,1,1)]:
        ov = data[k]; mm, h = ci(ov)
        e = m(by_diff(CELLS[k], "easy")); md = m(by_diff(CELLS[k], "medium")); hd = m(by_diff(CELLS[k], "hard"))
        print(f"{LABEL[k]:22s} {mm:.4f}±{h:.4f} {e:7.3f} {md:7.3f} {hd:7.3f}  {len(ov)}")

    print("\n— 三手段边际效应(固定另两者,4 对比的平均 Δ;Welch t 合并)—")
    for name, idx in [("RAG", 1), ("PE", 0), ("FT", 2)]:
        deltas = []
        on_all, off_all = [], []
        for k in CELLS:
            if k[idx] == 0:
                k_on = tuple(1 if i == idx else k[i] for i in range(3))
                d_on, d_off = data[k_on], data[k]
                deltas.append(m(d_on) - m(d_off))
                on_all += d_on; off_all += d_off
        t, p = stats.ttest_ind(on_all, off_all, equal_var=False)
        print(f"  开启 {name:4s} 的平均 Δ = {sum(deltas)/len(deltas):+.4f}  (4 格对比;合并 Welch p={p:.4f})")

    print("\n— 关键单元对比(Welch t)—")
    def cmp(a, b, la, lb):
        A, B = data[a], data[b]
        t, p = stats.ttest_ind(A, B, equal_var=False)
        print(f"  {la:16s} − {lb:16s}: Δ={m(A)-m(B):+.4f}  p={p:.4f}  {'✅' if p<0.05 else '❌噪声内'}")
    cmp((0,1,0),(0,0,0),"RAG only","baseline")
    cmp((1,1,0),(0,1,0),"PE+RAG","RAG only")
    cmp((0,1,1),(0,1,0),"RAG+FT","RAG only")
    cmp((1,1,1),(1,1,0),"All","PE+RAG")


if __name__ == "__main__":
    main()
