"""M23:CPython工业级六格消融。对比werkzeug小项目,逐条判工业级保持性。双裁判,用例配对。"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P=Path(__file__).resolve().parent.parent/"results"/"phaseE"
# 六格 -> 分数文件名
CELL={"baseline":"baseline","PE_only":"pe","RAG_only":"full","FT_only":"ftonly",
      "PE+RAG":"perag","PE+FT":"peft","All":"all"}
def load(name,tag):
    f=P/f"scores_cpy_{name}_{tag}.json"
    if not f.exists(): return None
    d=json.load(open(f,encoding="utf-8")); acc={}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"],[]).append(c["score"])
    return {k:sum(v)/len(v) for k,v in acc.items()}
def pair(a,b):
    ids=sorted(set(a)&set(b)); n=len(ids)
    t,p=stats.ttest_rel([a[i] for i in ids],[b[i] for i in ids])
    return sum(a[i]-b[i] for i in ids)/n, p, n

# werkzeug 小项目六格(E36/M10)参照
WZ={"baseline":0.185,"PE_only":0.107,"RAG_only":0.774,"FT_only":0.228,"PE+RAG":0.793,"All":0.796}
for tag,jlab in [("coderjudge","Coder"),("internjudge","internLM")]:
    print("="*70); print(f"裁判 = 独立 {jlab}"); print("="*70)
    sc={k:load(v,tag) for k,v in CELL.items()}
    if any(v is None for v in sc.values()): print("  缺分数文件,跳过"); continue
    print(f"{'格':<10}{'CPython':>9}{'werkzeug':>10}")
    for k in CELL:
        wz=WZ.get(k,'-'); wzs=f"{wz:.3f}" if isinstance(wz,float) else "-"
        m=sum(sc[k].values())/len(sc[k])
        print(f"{k:<10}{m:>9.3f}{wzs:>10}")
    print("\n关键对照(CPython工业级,用例配对):")
    for lab,a,b in [("RAG主导 (RAG_only−baseline)","RAG_only","baseline"),
                    ("PE增益 (PE+RAG−RAG_only)","PE+RAG","RAG_only"),
                    ("FT增益 (All−PE+RAG)","All","PE+RAG"),
                    ("FT only vs baseline","FT_only","baseline"),
                    ("PE only vs baseline","PE_only","baseline")]:
        d,p,n=pair(sc[a],sc[b]); sig="显著" if p<0.05 else "ns"
        print(f"  {lab:<32} Δ={d:+.3f} p={p:.3f} ({sig}, n={n})")
    print()
