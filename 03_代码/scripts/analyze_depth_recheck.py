"""M12 任务一:核心结论在新检索深度(rerank_candidates=80)下复查。
对每个核心格,对比 旧深度(12)vs 新深度(80)的 overall + reverse,并重判核心结论。

用法:python scripts/analyze_depth_recheck.py
"""

import json
import math
import sys
from pathlib import Path

from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"

# (标签, 旧深度文件, 新深度文件)。无 RAG 的格深度无关,新=旧。
CELLS = [
    ("baseline(none,无RAG)", "cell_baseline", "cell_baseline"),
    ("RAG only(plain)", "werkzeug_full_general", "werkzeug_full_general_deep"),
    ("PE only(无RAG)", "cell_pe_only", "cell_pe_only"),
    ("PE System+RAG", "werkzeug_pe_system", "werkzeug_pe_system_deep"),
    ("PE+RAG(System+CoT)", "werkzeug_pe_cot", "werkzeug_pe_cot_deep"),
    ("PE+RAG+领域fewshot", "werkzeug_pe_domain", "werkzeug_pe_domain_deep"),
    ("RAG+FT", "cell_rag_ft", "cell_rag_ft_deep"),
    ("All(PE+RAG+FT)", "cell_all", "cell_all_deep"),
]


def ov(name, filt=None):
    try:
        d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))["runs"]
    except FileNotFoundError:
        return None
    out = []
    for run in d:
        xs = [c["score"] for c in run if (filt is None or filt(c))]
        if xs:
            out.append(sum(xs) / len(xs))
    return out


def m(xs):
    return sum(xs) / len(xs)


def welch(a, b):
    if not a or not b:
        return float("nan"), float("nan")
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return m(a) - m(b), p


def main():
    print("=" * 84)
    print("M12 任务一:核心格 旧深度(rerank=12)vs 新深度(rerank=80),n=15")
    print("=" * 84)
    print(f"{'格':24s} {'旧overall':>10s} {'新overall':>10s} {'Δ深度':>9s} {'旧rev':>7s} {'新rev':>7s}")
    data = {}
    for label, old, new in CELLS:
        o_old, o_new = ov(old), ov(new)
        data[label] = (o_old, o_new)
        if o_old is None or o_new is None:
            print(f"{label:24s}  缺文件 old={old} new={new}")
            continue
        rold = ov(old, lambda c: "reverse" in c["category"]) or [0]
        rnew = ov(new, lambda c: "reverse" in c["category"]) or [0]
        d = m(o_new) - m(o_old)
        same = "(深度无关)" if old == new else ""
        print(f"{label:24s} {m(o_old):10.4f} {m(o_new):10.4f} {d:+9.4f} {m(rold):7.3f} {m(rnew):7.3f} {same}")

    def g(label):
        return data.get(label, (None, None))

    print("\n— 核心结论在新深度下复查 —")
    # RAG 杠杆
    rag_new = g("RAG only(plain)")[1]; base_new = g("baseline(none,无RAG)")[1]
    if rag_new and base_new:
        d, p = welch(rag_new, base_new)
        print(f"① RAG 杠杆(RAG only − baseline,新深度): Δ={d:+.4f} p={p:.2e} {'✅更稳' if p<0.01 else ''}")
    # CoT 边际(新 vs 旧)
    cot_new = g("PE+RAG(System+CoT)")[1]; ragonly_new = g("RAG only(plain)")[1]
    cot_old = g("PE+RAG(System+CoT)")[0]; ragonly_old = g("RAG only(plain)")[0]
    if cot_new and ragonly_new:
        dn, pn = welch(cot_new, ragonly_new); do, po = welch(cot_old, ragonly_old)
        print(f"② CoT 边际:旧深度 Δ={do:+.4f}(p={po:.3f}) → 新深度 Δ={dn:+.4f}(p={pn:.3f}) "
              f"[{'变小/消失' if abs(dn)<abs(do) else '变大'}]")
    # System 边际
    sys_new = g("PE System+RAG")[1]
    if sys_new and ragonly_new:
        d, p = welch(sys_new, ragonly_new)
        print(f"   System-only 边际(新深度): Δ={d:+.4f} p={p:.3f} {'✅' if p<0.05 else '❌噪声内'}")
    # FT 出局
    all_new = g("All(PE+RAG+FT)")[1]; ragft_new = g("RAG+FT")[1]
    if all_new and cot_new:
        d, p = welch(all_new, cot_new)
        print(f"③ FT 出局:All − PE+RAG(新深度) Δ={d:+.4f} p={p:.3f} {'✅仍无增量' if p>0.05 else '⚠改变'}")
    if ragft_new and ragonly_new:
        d, p = welch(ragft_new, ragonly_new)
        print(f"   RAG+FT − RAG only(新深度) Δ={d:+.4f} p={p:.3f} {'✅仍无增量' if p>0.05 else '⚠改变'}")
    # PE only < baseline
    peonly = g("PE only(无RAG)")[1]; base = g("baseline(none,无RAG)")[1]
    if peonly and base:
        d, p = welch(peonly, base)
        print(f"④ PE only − baseline(无RAG,深度无关): Δ={d:+.4f} p={p:.3f} {'✅仍<baseline' if d<0 else '⚠改变'}")


if __name__ == "__main__":
    main()
