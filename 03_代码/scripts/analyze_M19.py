"""M19:图表示梯度 B0/B1/B2 分析。逐格 vs B0,overall + 分类型(尤其 indirect),双裁判。"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent.parent / "results" / "phaseC"
REPS=["B0","B1","B2"]; JUDGES=[("coderjudge","Coder"),("internjudge","internLM")]

def load(rep, tag):
    d=json.load(open(P/f"scores_{rep}_{tag}.json",encoding="utf-8"))
    acc={}; cat={}
    for run in d["runs"]:
        for c in run:
            acc.setdefault(c["id"],[]).append(c["score"]); cat[c["id"]]=c.get("category","?")
    return {k:sum(v)/len(v) for k,v in acc.items()}, cat

for tag,jlab in JUDGES:
    print("="*70); print(f"裁判 = 独立 {jlab}"); print("="*70)
    sc={}; cat=None
    for r in REPS: sc[r],cat=load(r,tag)
    ids=sorted(set(sc["B0"]))
    # overall
    print(f"{'类型':<16}{'n':>4}  {'B0':>7} {'B1':>7} {'B2':>7}   B1-B0      B2-B0")
    cats=["forward_dep","reverse_dep","symbol_location","inheritance","indirect_dep","__ALL__"]
    for ct in cats:
        sub=[i for i in ids if (ct=='__ALL__' or cat[i]==ct)]
        if not sub: continue
        m={r:sum(sc[r][i] for i in sub)/len(sub) for r in REPS}
        def pair(a,b):
            t,p=stats.ttest_rel([sc[a][i] for i in sub],[sc[b][i] for i in sub]); return sum(sc[a][i]-sc[b][i] for i in sub)/len(sub),p
        M10,p10=pair("B1","B0"); M20,p20=pair("B2","B0")
        s1='*' if p10<0.05 else ' '; s2='*' if p20<0.05 else ' '
        print(f"{ct:<16}{len(sub):>4}  {m['B0']:>7.3f} {m['B1']:>7.3f} {m['B2']:>7.3f}   {M10:+.3f}{s1}(p={p10:.3f}) {M20:+.3f}{s2}(p={p20:.3f})")
    print()
