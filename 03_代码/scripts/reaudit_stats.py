"""外部评委指控核实:正确统计单位(56用例配对) + 独立裁判(cj)交叉复核。
铁律:用数据说话,成立就认。
"""
import json, re, math, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
R = Path(__file__).resolve().parent.parent / "results"

def per_case_mean(name):
    """返回 {id: 跨15run平均score}, 以及 {id: difficulty}。"""
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    acc, diff = {}, {}
    for run in d["runs"]:
        for c in run:
            acc.setdefault(c["id"], []).append(c["score"])
            diff[c["id"]] = c["difficulty"]
    return {k: sum(v)/len(v) for k, v in acc.items()}, diff, len(d["runs"])

def run_means(name):
    """老口径:每run一个overall(15个数)。"""
    d = json.load(open(R / f"multi_{name}.json", encoding="utf-8"))
    out = []
    for run in d["runs"]:
        s = [c["score"] for c in run]
        out.append(sum(s)/len(s))
    return out

def paired_56(name_a, name_b, label):
    a, _, na = per_case_mean(name_a)
    b, _, nb = per_case_mean(name_b)
    ids = sorted(set(a) & set(b))
    da = [a[i]-b[i] for i in ids]
    n = len(ids)
    md = sum(da)/n
    sd = math.sqrt(sum((x-md)**2 for x in da)/(n-1))
    se = sd/math.sqrt(n)
    t, p = stats.ttest_rel([a[i] for i in ids], [b[i] for i in ids])
    h = stats.t.ppf(0.975, n-1)*se
    # 老口径对照
    ra, rb = run_means(name_a), run_means(name_b)
    t2, p2 = stats.ttest_ind(ra, rb, equal_var=False)
    print(f"\n=== {label}  ({name_a} - {name_b}) ===")
    print(f"  老口径(15 run-means, 非配对): delta={sum(ra)/len(ra)-sum(rb)/len(rb):+.4f}  p={p2:.2e}")
    print(f"  正确口径(n={n} 用例, 配对 t): delta={md:+.4f}  95%CI=[{md-h:+.4f},{md+h:+.4f}]  p={p:.4f}  {'显著' if p<0.05 else '不显著'}")
    return md, p

print("="*72); print("指控二复算:正确统计单位 = 56 用例配对 t 检验"); print("="*72)
paired_56("werkzeug_full_general", "werkzeug_baseline_general", "RAG 主效应 (full - baseline)")
paired_56("werkzeug_pe_cot", "werkzeug_full_general", "CoT 增益 (pe_cot - full)")
paired_56("werkzeug_pe_system", "werkzeug_full_general", "System-prompt (pe_system - full)")
paired_56("werkzeug_pe_domain", "werkzeug_pe_cot", "领域 few-shot (pe_domain - pe_cot)")
paired_56("cell_all", "werkzeug_pe_cot", "+FT (all - pe_cot)")
# deep 口径
paired_56("werkzeug_pe_cot_deep", "werkzeug_full_general_deep", "CoT 增益 deep口径")

# ---- 独立裁判 cj 交叉复核 ----
def cj_scores(fname):
    d = json.load(open(R.parent / fname, encoding="utf-8")) if (R.parent/fname).exists() else json.load(open(R/fname, encoding="utf-8"))
    out = {}
    for item in d:
        ans = item["answer"]
        m = re.search(r'"score"\s*:\s*([0-9.]+)', ans)
        if m: out[item["id"]] = float(m.group(1))
    return out

print("\n"+"="*72); print("指控一复核:独立裁判(Coder判general答案, gen≠judge) cj 交叉"); print("="*72)
import os
cjdir = R.parent
def load_cj(name):
    for base in (cjdir, R):
        p = base / name
        if p.exists(): return cj_scores(p.name) if base==cjdir else cj_scores(p.name)
    return None

def cj_compare(fa, fb, label):
    a = cj_scores(fa); b = cj_scores(fb)
    if not a or not b: print(f"  {label}: 缺文件"); return
    ids = sorted(set(a)&set(b))
    da = [a[i]-b[i] for i in ids]; n=len(ids); md=sum(da)/n
    t,p = stats.ttest_rel([a[i] for i in ids],[b[i] for i in ids])
    print(f"  {label}: 独立裁判 delta={md:+.4f} (n={n}) p={p:.4f}  meanA={sum(a.values())/len(a):.3f} meanB={sum(b.values())/len(b):.3f}")

# 文件在 results/ 下
def find(name):
    for base in (R, cjdir):
        if (base/name).exists(): return base/name
    return None
def cj2(name):
    p=find(name);
    if not p: return None
    d=json.load(open(p,encoding="utf-8")); out={}
    for it in d:
        m=re.search(r'"score"\s*:\s*([0-9.]+)', it["answer"])
        if m: out[it["id"]]=float(m.group(1))
    return out
def cmp2(na,nb,label):
    a=cj2(na); b=cj2(nb)
    if a is None or b is None: print(f"  {label}: 缺 {na if a is None else nb}"); return
    ids=sorted(set(a)&set(b)); da=[a[i]-b[i] for i in ids]; n=len(ids); md=sum(da)/n
    t,p=stats.ttest_rel([a[i] for i in ids],[b[i] for i in ids])
    print(f"  {label}: delta={md:+.4f} n={n} p={p:.4f}  meanA={sum(a[i] for i in ids)/n:.3f} meanB={sum(b[i] for i in ids)/n:.3f}")

cmp2("judgeanswers_werkzeug_full_qwen_cj.json","judgeanswers_werkzeug_baseline_qwen_cj.json","RAG主效应 full-baseline (独立Coder裁判)")
cmp2("judgeanswers_werkzeug_pe_cot_cj.json","judgeanswers_werkzeug_full_general_cj.json","CoT增益 pecot-full (独立Coder裁判)")
