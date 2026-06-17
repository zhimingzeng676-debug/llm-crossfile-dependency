"""M17 Phase A 分析:生成固定,3 裁判(self=qwen / 独立coder / 独立intern)对照。
每条件取均值;关键对比用 56 用例配对 t。横向看结论在自判 vs 两独立裁判下是否一致。
"""
import json, sys, math
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent.parent / "results" / "phaseA"

CONDS = ["baseline_general","purellm_general","graphcards_general","full_general",
         "pe_system","pe_cot","pe_domain"]
JUDGES = [("qwenjudge","self判(Qwen=gen)"),("coderjudge","独立Coder"),("internjudge","独立internLM")]

def scores(cond, tag):
    f = P / f"scores_{cond}_{tag}.json"
    if not f.exists(): return None
    d = json.load(open(f, encoding="utf-8"))
    run = d["runs"][0]  # 单run
    return {c["id"]: c["score"] for c in run}

def paired(a, b):
    ids = sorted(set(a) & set(b))
    da = [a[i]-b[i] for i in ids]; n=len(ids); md=sum(da)/n
    t,p = stats.ttest_rel([a[i] for i in ids],[b[i] for i in ids])
    return md, p, n

print("="*78)
print("各条件 overall(3 裁判对照,生成固定)")
print("="*78)
print(f"{'条件':<22}", *[f"{lab:<14}" for _,lab in JUDGES])
for cond in CONDS:
    row=[]
    for tag,_ in JUDGES:
        s=scores(cond,tag)
        row.append(f"{sum(s.values())/len(s):.3f}" if s else "  --  ")
    print(f"{cond:<22}", *[f"{v:<14}" for v in row])

print("\n"+"="*78)
print("关键对比(56 用例配对 t):看结论在自判 vs 独立裁判下是否一致")
print("="*78)
COMPS = [("full_general","baseline_general","RAG主效应 full-baseline"),
         ("graphcards_general","purellm_general","图卡片RAG vs 纯LLM"),
         ("pe_cot","full_general","CoT增益 pecot-full"),
         ("pe_system","full_general","System-prompt pesys-full"),
         ("pe_domain","pe_cot","领域few-shot pedom-pecot")]
for na,nb,lab in COMPS:
    print(f"\n[{lab}]")
    for tag,jlab in JUDGES:
        a,b=scores(na,tag),scores(nb,tag)
        if not a or not b: print(f"  {jlab:<16} --缺文件--"); continue
        md,p,n=paired(a,b)
        sig="显著" if p<0.05 else "不显著"
        print(f"  {jlab:<16} delta={md:+.4f}  p={p:.4f}  ({sig}, n={n})")
