"""M38-40 任务一+二:大样本脏依赖 judge-independent 确定性打分。
两个分开的确定性指标(零 LLM):
  - detect(识破率):答案是否点出"存在脏依赖"(可选/条件/动态/反射/运行时,gold_detect 标记命中)。
  - complete(精确补全率):答案是否**具体补出**脏依赖——命中具体模块 token(gold_complete) 且 命中机制 token(gold_mech)。
按 (条件 × 脏类型) 聚合,算 detect/complete/gap;机理实验比较 humble/humble_source/humble_prompt。
真值来自 data/dirty_large.json(源码独立抽取,与 RAG 卡片解耦)。
"""
import json, re, sys
from pathlib import Path
from scipy.stats import ttest_rel
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DL = ROOT/"results"/"dirty_large"
cases = {c["id"]: c for c in json.load(open(ROOT/"data"/"dirty_large.json", encoding="utf-8"))}

def present(tok, text):
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', tok):  # 英文标识符:词边界,防子串误命中
        t = re.escape(tok)
        return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None
    return tok.lower() in text.lower()  # 中文/符号:子串

def detect_hit(c, text):
    return any(present(m, text) for m in c["gold_detect"])
def complete_hit(c, text):
    return any(present(m, text) for m in c["gold_complete"]) and any(present(m, text) for m in c["gold_mech"])

def score_condition(cond):
    fp = DL/f"ans_{cond}.json"
    if not fp.exists(): return None
    runs = json.load(open(fp, encoding="utf-8"))["runs"]
    per_det, per_com = {}, {}   # id -> [0/1 per run]
    for run in runs:
        for x in run:
            c = cases.get(x["id"])
            if not c: continue
            per_det.setdefault(x["id"], []).append(1 if detect_hit(c, x["answer"]) else 0)
            per_com.setdefault(x["id"], []).append(1 if complete_hit(c, x["answer"]) else 0)
    ids = list(per_det)
    def case_rate(d, i): return sum(d[i])/len(d[i])
    return {"ids": ids, "det": {i: case_rate(per_det, i) for i in ids},
            "com": {i: case_rate(per_com, i) for i in ids}}

CONDS = ["strict", "humble", "baseline", "humble_source", "humble_prompt"]
scored = {c: score_condition(c) for c in CONDS}
scored = {k: v for k, v in scored.items() if v}
if not scored:
    print("答案未就绪(ans_*.json 缺)。先取回远端结果再运行。"); sys.exit(0)

TYPES = sorted(set(c["dirty_type"] for c in cases.values()))
report = {"n_cases": len(cases), "by_condition": {}, "by_type": {}, "mechanism": {}, "stats": {}}

for cond, s in scored.items():
    ids = s["ids"]
    det = sum(s["det"][i] for i in ids)/len(ids)
    com = sum(s["com"][i] for i in ids)/len(ids)
    report["by_condition"][cond] = {"n": len(ids), "detect": round(det, 3),
                                    "complete": round(com, 3), "gap": round(det-com, 3)}

# 按脏类型(每条件)
for cond, s in scored.items():
    report["by_type"][cond] = {}
    for t in TYPES:
        tids = [i for i in s["ids"] if cases[i]["dirty_type"] == t]
        if not tids: continue
        report["by_type"][cond][t] = {
            "n": len(tids),
            "detect": round(sum(s["det"][i] for i in tids)/len(tids), 3),
            "complete": round(sum(s["com"][i] for i in tids)/len(tids), 3)}

# 机理实验:humble vs humble_source vs humble_prompt 的 complete(determinable 子集,补全才可能)
det_ids = [i for i in cases if cases[i]["determinable"]]
for cond in ["humble", "humble_source", "humble_prompt"]:
    if cond in scored:
        s = scored[cond]; ids = [i for i in det_ids if i in s["com"]]
        report["mechanism"][cond] = {
            "n_determinable": len(ids),
            "complete_determinable": round(sum(s["com"][i] for i in ids)/len(ids), 3),
            "detect_determinable": round(sum(s["det"][i] for i in ids)/len(ids), 3)}

# 配对统计:humble vs strict(detect)、humble_source vs humble(complete,determinable)
def paired(a, b, key, ids):
    va = [scored[a][key][i] for i in ids]; vb = [scored[b][key][i] for i in ids]
    t, p = ttest_rel(va, vb)
    return {"mean_a": round(sum(va)/len(va), 3), "mean_b": round(sum(vb)/len(vb), 3),
            "delta": round((sum(va)-sum(vb))/len(va), 3), "t": round(float(t), 3), "p": float(p), "n": len(ids)}
if "humble" in scored and "strict" in scored:
    cids = [i for i in scored["humble"]["ids"] if i in scored["strict"]["det"]]
    report["stats"]["humble_vs_strict_DETECT"] = paired("humble", "strict", "det", cids)
if "humble_source" in scored and "humble" in scored:
    cids = [i for i in det_ids if i in scored["humble_source"]["com"] and i in scored["humble"]["com"]]
    report["stats"]["humble_source_vs_humble_COMPLETE_determinable"] = paired("humble_source", "humble", "com", cids)
if "humble_prompt" in scored and "humble" in scored:
    cids = [i for i in det_ids if i in scored["humble_prompt"]["com"] and i in scored["humble"]["com"]]
    report["stats"]["humble_prompt_vs_humble_COMPLETE_determinable"] = paired("humble_prompt", "humble", "com", cids)

json.dump(report, open(DL/"score_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("=== 大样本脏依赖 judge-independent 打分(N =", report["n_cases"], "案例) ===")
print("\n[识破率 vs 精确补全率,按条件]")
for cond, r in report["by_condition"].items():
    print(f"  {cond:14s} n={r['n']}  detect={r['detect']:.0%}  complete={r['complete']:.0%}  gap(识破−补全)={r['gap']:+.0%}")
print("\n[按脏类型:detect / complete]")
for cond in ["strict", "humble"]:
    if cond in report["by_type"]:
        print(f"  {cond}:")
        for t, r in report["by_type"][cond].items():
            print(f"     {t:12s} n={r['n']}  detect={r['detect']:.0%}  complete={r['complete']:.0%}")
print("\n[机理实验(determinable 子集,补全才可能)]")
for cond, r in report["mechanism"].items():
    print(f"  {cond:14s} n={r['n_determinable']}  complete={r['complete_determinable']:.0%}  detect={r['detect_determinable']:.0%}")
print("\n[配对统计]")
for k, v in report["stats"].items():
    print(f"  {k}: {v['mean_a']} vs {v['mean_b']} (Δ{v['delta']:+}, t={v['t']}, p={v['p']:.2e}, n={v['n']})")
print("\n写出", DL/"score_report.json")
