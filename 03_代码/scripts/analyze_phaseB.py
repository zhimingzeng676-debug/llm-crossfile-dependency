"""M17 Phase B 分析:deep(rerank=80)头条条件 n=15 重生成,双独立裁判,56 配对+CI。
洗净原 self-judge 的 deep 0.94 头条数字。
"""
import json, sys, math
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent.parent / "results" / "phaseB"
CONDS = ["baseline","full_deep","pecot_deep"]
JUDGES = [("coderjudge","独立Coder"),("internjudge","独立internLM")]

def per_case(cond, tag):
    d = json.load(open(P / f"scores_b_{cond}_{tag}.json", encoding="utf-8"))
    acc = {}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"], []).append(c["score"])
    return {k: sum(v)/len(v) for k,v in acc.items()}, len(d["runs"])

def ci(cond, tag):
    pc,nr = per_case(cond, tag)
    runs = json.load(open(P/f"scores_b_{cond}_{tag}.json",encoding="utf-8"))["runs"]
    ov = [sum(c["score"] for c in r)/len(r) for r in runs]  # run-level overall for CI display
    m = sum(ov)/len(ov); sd=math.sqrt(sum((x-m)**2 for x in ov)/(len(ov)-1)); se=sd/math.sqrt(len(ov))
    h=stats.t.ppf(0.975,len(ov)-1)*se
    return pc, m, (m-h,m+h), nr

def paired(a,b):
    ids=sorted(set(a)&set(b)); n=len(ids)
    t,p=stats.ttest_rel([a[i] for i in ids],[b[i] for i in ids])
    md=sum(a[i]-b[i] for i in ids)/n
    return md,p,n

print("="*72); print("Phase B:deep(rerank=80)条件 n=15,双独立裁判"); print("="*72)
pc={}
for tag,jlab in JUDGES:
    print(f"\n[{jlab}]")
    for cond in CONDS:
        p_,m,(lo,hi),nr=ci(cond,tag); pc[(cond,tag)]=p_
        print(f"  {cond:12s} overall={m:.4f}  95%CI=[{lo:.4f},{hi:.4f}]  (n={nr}run)")

print("\n"+"="*72); print("deep 关键对比(56 用例配对)"); print("="*72)
for tag,jlab in JUDGES:
    rag=paired(pc[("full_deep",tag)],pc[("baseline",tag)])
    cot=paired(pc[("pecot_deep",tag)],pc[("full_deep",tag)])
    print(f"\n[{jlab}]")
    print(f"  deep RAG主效应 full_deep−baseline: delta={rag[0]:+.4f} p={rag[1]:.2e} ({'显著' if rag[1]<0.05 else 'ns'})")
    print(f"  deep CoT       pecot_deep−full_deep: delta={cot[0]:+.4f} p={cot[1]:.4f} ({'显著' if cot[1]<0.05 else 'ns'})")
