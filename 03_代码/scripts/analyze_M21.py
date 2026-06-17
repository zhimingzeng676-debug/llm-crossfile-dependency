"""M21:CPython大项目 baseline vs full(大池检索),双独立裁判,用例配对,分类型(内部vs跨语言)。"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P=Path(__file__).resolve().parent.parent/"results"/"phaseE"
def per_case(cond,tag):
    f=P/f"scores_cpy_{cond}_{tag}.json"
    if not f.exists(): return None,None
    d=json.load(open(f,encoding="utf-8")); acc={}; cat={}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"],[]).append(c["score"]); cat[c["id"]]=c.get("category","?")
    return {k:sum(v)/len(v) for k,v in acc.items()}, cat
print("="*70); print("M21 CPython大项目(1456卡片池):baseline vs full"); print("="*70)
for tag,jlab in [("coderjudge","Coder"),("internjudge","internLM")]:
    b,_=per_case("baseline",tag); f,cat=per_case("full",tag)
    if not b or not f: print(f"{jlab}: 缺"); continue
    ids=sorted(set(b)&set(f)); n=len(ids)
    mb=sum(b[i] for i in ids)/n; mf=sum(f[i] for i in ids)/n
    t,p=stats.ttest_rel([f[i] for i in ids],[b[i] for i in ids])
    print(f"\n[{jlab}] baseline={mb:.3f} full={mf:.3f} full-base={mf-mb:+.3f} p={p:.2e} (n={n})")
    bycat={}
    for i in ids: bycat.setdefault(cat[i],[]).append((b[i],f[i]))
    for ct,v in sorted(bycat.items()):
        mbb=sum(x[0] for x in v)/len(v); mff=sum(x[1] for x in v)/len(v)
        tag2='跨语言' if ct=='xlang' else '内部'
        print(f"    {ct:<12}({tag2},n={len(v)}): base={mbb:.2f} full={mff:.2f} Δ={mff-mbb:+.2f}")
