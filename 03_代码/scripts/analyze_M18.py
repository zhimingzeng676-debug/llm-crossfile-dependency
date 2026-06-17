"""M18:去循环金标准上 RAG 主效应复测,对比 tree-sitter 金标准(M17)。"""
import json, sys, math
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent.parent / "results" / "phaseB"

def per_case(cond, tag):
    d = json.load(open(P/f"scores_dec_{cond}_{tag}.json", encoding="utf-8"))
    acc = {}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"], []).append(c["score"])
    return {k: sum(v)/len(v) for k,v in acc.items()}, len(d["runs"])

def overall_ci(cond, tag):
    runs = json.load(open(P/f"scores_dec_{cond}_{tag}.json",encoding="utf-8"))["runs"]
    ov=[sum(c["score"] for c in r)/len(r) for r in runs]
    m=sum(ov)/len(ov); sd=math.sqrt(sum((x-m)**2 for x in ov)/(len(ov)-1)); h=stats.t.ppf(0.975,len(ov)-1)*sd/math.sqrt(len(ov))
    return m,(m-h,m+h)

print("="*72); print("M18 去循环金标准(40条,gold=ast独立+人工核验,非tree-sitter卡片管线)"); print("="*72)
print("对比基准:M17 tree-sitter金标准 deep RAG主效应 = Coder +0.728 / internLM +0.768\n")
for tag,jlab in [("coderjudge","独立Coder"),("internjudge","独立internLM")]:
    b,nb=per_case("baseline",tag); f,nf=per_case("full_deep",tag)
    bm,bci=overall_ci("baseline",tag); fm,fci=overall_ci("full_deep",tag)
    ids=sorted(set(b)&set(f)); n=len(ids)
    md=sum(f[i]-b[i] for i in ids)/n
    t,p=stats.ttest_rel([f[i] for i in ids],[b[i] for i in ids])
    print(f"[{jlab}]  baseline={bm:.4f}{bci}  full_deep={fm:.4f}{fci}")
    print(f"   去循环 RAG主效应 full_deep-baseline: delta={md:+.4f}  p={p:.2e}  (n={n}配对)\n")
