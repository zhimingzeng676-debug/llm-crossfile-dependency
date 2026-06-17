"""M20:跨语言泛化分析。每语言 baseline vs full(结构化卡片),双独立裁判,用例配对。"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent.parent / "results" / "phaseD"
LANGS=[("go","Go/gin"),("java","Java/gson"),("c","C/lua")]
JUDGES=[("coderjudge","Coder"),("internjudge","internLM")]

def per_case(lang,cond,tag):
    f=P/f"scores_{lang}_{cond}_{tag}.json"
    if not f.exists(): return None,None
    d=json.load(open(f,encoding="utf-8")); acc={}; cat={}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"],[]).append(c["score"]); cat[c["id"]]=c.get("category","?")
    return {k:sum(v)/len(v) for k,v in acc.items()}, cat

print("="*72); print("M20 跨语言:结构化依赖卡片(full) vs baseline(无RAG)"); print("="*72)
for tag,jlab in JUDGES:
    print(f"\n###### 独立裁判 = {jlab} ######")
    print(f"{'语言':<12}{'baseline':>9}{'full':>9}{'full-base':>11}{'p':>9}{'n':>5}")
    for lang,llab in LANGS:
        b,_=per_case(lang,"baseline",tag); f,cat=per_case(lang,"full",tag)
        if not b or not f: print(f"{llab:<12} --缺--"); continue
        ids=sorted(set(b)&set(f)); n=len(ids)
        mb=sum(b[i] for i in ids)/n; mf=sum(f[i] for i in ids)/n
        t,p=stats.ttest_rel([f[i] for i in ids],[b[i] for i in ids])
        print(f"{llab:<12}{mb:>9.3f}{mf:>9.3f}{mf-mb:>+11.3f}{p:>9.1e}{n:>5}")
        # 分类型(full)
        bycat={}
        for i in ids: bycat.setdefault(cat[i],[]).append((b[i],f[i]))
        seg=" | ".join(f"{ct}: {sum(x[1] for x in v)/len(v):.2f}vs{sum(x[0] for x in v)/len(v):.2f}" for ct,v in sorted(bycat.items()))
        print(f"             分类型(full vs base): {seg}")
