"""M27:新工作去循环幅度 vs 原同源幅度,量化循环贡献占比。同子集对比。"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
R=Path(__file__).resolve().parent.parent/"results"
# proj -> (原始scores目录, 原始前缀)
ORIG={"lua":(R/"phaseD","c"),"gson":(R/"phaseD","java"),"go":(R/"phaseD","go"),"cpy":(R/"phaseE","cpy")}
DEC=R/"phaseH"
def load(path,prefix,cond,tag,scoredir=None):
    f=path/f"scores_{prefix}_{cond}_{tag}.json"
    if not f.exists(): return None
    d=json.load(open(f,encoding="utf-8")); acc={}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"],[]).append(c["score"])
    return {k:sum(v)/len(v) for k,v in acc.items()}
def load_dec(proj,cond,tag):
    f=DEC/f"scores_dec27_{proj}_{cond}_{tag}.json"
    if not f.exists(): return None
    d=json.load(open(f,encoding="utf-8")); acc={}
    for run in d["runs"]:
        for c in run: acc.setdefault(c["id"],[]).append(c["score"])
    return {k:sum(v)/len(v) for k,v in acc.items()}
print("="*72); print("M27 新工作去循环:同源gold幅度 vs 去循环gold幅度(同子集,独立Coder裁判)"); print("="*72)
print(f"{'项目':<8}{'n':>4}{'同源full-base':>14}{'去循环full-base':>16}{'循环贡献':>10}")
for proj,(od,pre) in ORIG.items():
    decb=load_dec(proj,"baseline","coderjudge"); decf=load_dec(proj,"full","coderjudge")
    if not decb or not decf: print(f"{proj:<8} (缺去循环分数)"); continue
    ids=sorted(set(decb)&set(decf))
    ob=load(od,pre,"baseline","coderjudge"); of=load(od,pre,"full","coderjudge")
    # 原始margin限同子集
    oids=[i for i in ids if ob and i in ob and i in of]
    om=(sum(of[i]-ob[i] for i in oids)/len(oids)) if oids else float('nan')
    dm=sum(decf[i]-decb[i] for i in ids)/len(ids)
    circ=om-dm
    print(f"{proj:<8}{len(ids):>4}{om:>14.3f}{dm:>16.3f}{circ:>+10.3f}")
print("\n循环贡献 = 同源gold幅度 − 去循环gold幅度(正=同源略高估,即循环成分)")
