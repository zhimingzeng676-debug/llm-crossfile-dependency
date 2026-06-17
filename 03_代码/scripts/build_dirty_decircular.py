"""M41 任务一+二:矛盾数字彻查 + 去循环真值。
统一一个 complete 口径,在全样本 N=103 + determinable/non-det 分区上算;
并入 humble_source_masked(答案遮蔽的去循环真值),给出:
  - 三处打架数字各自来源(同一概念不同子集/条件)
  - humble_source 90% 的同源循环成分 vs 去循环真值
  - 去循环后"信息可得性"提升是否还成立
全 judge-independent(零 LLM)。
"""
import json, re, sys
from pathlib import Path
from scipy.stats import ttest_rel
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DL = ROOT/"results"/"dirty_large"
cases = {c["id"]: c for c in json.load(open(ROOT/"data"/"dirty_large.json", encoding="utf-8"))}

def present(tok, text):
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', tok):
        t = re.escape(tok); return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None
    return tok.lower() in text.lower()
def complete_hit(c, text):
    return any(present(m, text) for m in c["gold_complete"]) and any(present(m, text) for m in c["gold_mech"])
def load(cond):
    fp = DL/f"ans_{cond}.json"
    if not fp.exists(): return None
    per = {}
    for run in json.load(open(fp, encoding="utf-8"))["runs"]:
        for x in run:
            c = cases.get(x["id"])
            if c: per.setdefault(x["id"], []).append(1 if complete_hit(c, x["answer"]) else 0)
    return {i: sum(v)/len(v) for i, v in per.items()}

conds = ["humble", "humble_prompt", "humble_source", "humble_source_masked"]
S = {c: load(c) for c in conds}
S = {k: v for k, v in S.items() if v}
allids = list(cases)
det = [i for i in allids if cases[i]["determinable"]]       # snippet 100% 含答案 = 循环风险区
nondet = [i for i in allids if not cases[i]["determinable"]]  # snippet 不含答案 = 去循环

def m(d, ids):
    ids = [i for i in ids if i in d]; return sum(d[i] for i in ids)/len(ids) if ids else None
def paired(a, b, ids):
    ids = [i for i in ids if i in S[a] and i in S[b]]
    va = [S[a][i] for i in ids]; vb = [S[b][i] for i in ids]; t, p = ttest_rel(va, vb)
    return {"to": round(sum(va)/len(va),3), "from": round(sum(vb)/len(vb),3),
            "delta": round((sum(va)-sum(vb))/len(va),3), "t": round(float(t),2), "p": float(p), "n": len(ids)}

report = {"complete_by_condition_and_partition": {}, "circularity": {}, "paired": {}}
print("=== 矛盾数字溯源:同一'complete'在不同条件/子集 ===")
print(f"  §9.1 报的 42% = humble complete 全样本N=103 = {m(S['humble'],allids):.3f}")
print(f"  §9.2 报的 10% = humble complete determinable子集n=58 = {m(S['humble'],det):.3f}")
print(f"  score_report 84.5% = humble_SOURCE complete 全样本N=103 = {m(S['humble_source'],allids):.3f}")
print(f"  头条 90% = humble_SOURCE complete determinable子集n=58 = {m(S['humble_source'],det):.3f}")
print("  → 同一'补全率'在 {humble vs humble_source} × {全样本 vs determinable子集} 四格里取了最戏剧的一格当头条。")

for cond in S:
    report["complete_by_condition_and_partition"][cond] = {
        "all103": round(m(S[cond], allids), 3),
        "determinable58": round(m(S[cond], det), 3) if m(S[cond], det) is not None else None,
        "nondet45": round(m(S[cond], nondet), 3) if m(S[cond], nondet) is not None else None}

print("\n=== complete 三口径全表 ===")
print(f"  {'condition':22s} {'all103':>8s} {'det58':>8s} {'nondet45':>8s}")
for cond, r in report["complete_by_condition_and_partition"].items():
    d = r['determinable58']; nd = r['nondet45']
    print(f"  {cond:22s} {r['all103']:8.3f} {('%.3f'%d) if d is not None else '   -':>8s} {('%.3f'%nd) if nd is not None else '   -':>8s}")

# 去循环关键对比(determinable 子集上)
print("\n=== 去循环:determinable 子集补全的真假成分 ===")
hs_det = m(S['humble_source'], det)
report["circularity"]["snippet_contains_answer"] = f"{len(det)}/{len(allids)} (全部 determinable)"
if "humble_source_masked" in S:
    hsm = m(S['humble_source_masked'], det)
    print(f"  humble_source(源码含答案) determinable = {hs_det:.3f}  ← 含同源循环成分")
    print(f"  humble_source_MASKED(答案遮蔽) determinable = {hsm:.3f}  ← 去循环真值(结构在/答案抹掉,靠推断)")
    print(f"  循环成分 = {hs_det-hsm:+.3f}(纯读取被喂答案的虚高)")
    report["circularity"]["humble_source_det"] = round(hs_det,3)
    report["circularity"]["humble_source_masked_det"] = round(hsm,3)
    report["circularity"]["circular_component"] = round(hs_det-hsm,3)
hp_det = m(S['humble_prompt'], det)
print(f"  humble_prompt(只问不喂源码) determinable = {hp_det:.3f}  ← 纯参数知识召回(非循环,但=开源名记忆)")

print("\n=== 配对(去循环视角)===")
for name, a, b, ids in [
    ("humble_source vs humble  [determinable=循环]", "humble_source", "humble", det),
    ("humble_source vs humble  [nondet=去循环]", "humble_source", "humble", nondet),
    ("humble_source_masked vs humble [determinable,去循环]", "humble_source_masked", "humble", det),
    ("humble_source vs humble_source_masked [循环成分]", "humble_source", "humble_source_masked", det),
    ("humble_prompt vs humble [全样本,只问不喂]", "humble_prompt", "humble", allids)]:
    if a in S and b in S:
        r = paired(a, b, ids); report["paired"][name] = r
        print(f"  {name}: {r['from']}->{r['to']} (Δ{r['delta']:+}, t={r['t']}, p={r['p']:.2e}, n={r['n']})")

json.dump(report, open(DL/"decircular_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n写出", DL/"decircular_report.json")
