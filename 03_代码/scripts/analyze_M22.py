"""M22:B0/B1/B2/B3 完整对照,重点 B3 vs B2(完整图检索 vs 文本化物化)。双裁判,分类型。"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P=Path(__file__).resolve().parent.parent/"results"/"phaseC"
REPS=["B0","B1","B2","B3"]; JUDGES=[("coderjudge","Coder"),("internjudge","internLM")]
def load(rep,tag):
    f=P/f"scores_{rep}_{tag}.json"
    if not f.exists(): return None,None
    d=json.load(open(f,encoding="utf-8")); acc={};cat={}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"],[]).append(c["score"]); cat[c["id"]]=c.get("category","?")
    return {k:sum(v)/len(v) for k,v in acc.items()},cat
for tag,jlab in JUDGES:
    print("="*72); print(f"裁判 = 独立 {jlab}"); print("="*72)
    sc={}; cat=None; ok=True
    for r in REPS:
        sc[r],c=load(r,tag)
        if sc[r] is None: ok=False
        else: cat=c
    if not ok: print("  缺 B3 分数,跳过"); continue
    ids=sorted(set(sc["B0"])&set(sc["B3"]))
    cats=["forward_dep","reverse_dep","symbol_location","indirect_dep","__ALL__"]
    print(f"{'类型':<16}{'n':>4}  {'B0':>6} {'B1':>6} {'B2':>6} {'B3':>6}   {'B3-B2':>8} {'B3-B0':>8}")
    for ct in cats:
        sub=[i for i in ids if (ct=='__ALL__' or cat.get(i)==ct)]
        if not sub: continue
        m={r:sum(sc[r][i] for i in sub)/len(sub) for r in REPS}
        def pair(a,b):
            t,p=stats.ttest_rel([sc[a][i] for i in sub],[sc[b][i] for i in sub]); return sum(sc[a][i]-sc[b][i] for i in sub)/len(sub),p
        M32,p32=pair("B3","B2"); M30,p30=pair("B3","B0")
        s32='*' if p32<0.05 else ' '
        print(f"{ct:<16}{len(sub):>4}  {m['B0']:>6.3f} {m['B1']:>6.3f} {m['B2']:>6.3f} {m['B3']:>6.3f}   {M32:+.3f}{s32}(p={p32:.2f}) {M30:+.3f}(p={p30:.2f})")
    print()
