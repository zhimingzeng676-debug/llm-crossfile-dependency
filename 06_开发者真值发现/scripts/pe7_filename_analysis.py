"""
M51 Task1a (CPU): is no_card's invisible-layer recall explained by filename
similarity (coincidence) or filename-independent true capture?

For each invisible gold edge (seed X, gold Y) in evo_raw: compute filename/path
similarity; split by recalled-by-no_card vs missed. Key: recall on jaccard==0
(filename-dissimilar) invisible gold = candidate TRUE capture (not filename).
Judge-independent; co-change != dependency; no conclusion.
"""
import json, os, re
from collections import defaultdict
T3=r"D:\claude\59\pilot_devtruth\task3"

def toks(path):
    b=os.path.basename(path)
    b=b[:-3] if b.endswith(".py") else b
    return set(t for t in re.split(r"[_\W]+", b.lower()) if t)
def jacc(a,b):
    ta,tb=toks(a),toks(b)
    if not (ta|tb): return 0.0
    return len(ta&tb)/len(ta|tb)
def dir_sim(a,b):
    da,db=os.path.dirname(a).split("/"),os.path.dirname(b).split("/")
    common=0
    for x,y in zip(da,db):
        if x==y: common+=1
        else: break
    return common  # shared leading dir components

insts=json.load(open(os.path.join(T3,"instances_evo_raw.json")))
sc=json.load(open(os.path.join(T3,"scores_evo_raw.json")))
pred={(r["project"],r["seed"]):r["preds"] for r in sc["results"]}

# collect invisible gold edges with similarity + recall flags
rows=[]  # dict per edge
for inst in insts:
    key=(inst["project"],inst["seed"])
    if key not in pred: continue
    nc=set(pred[key].get("no_card",[])); scd=set(pred[key].get("static_card",[]))
    for g in inst["gold"]:
        lay=g["layer"]
        if not lay.startswith("invisible"): continue
        j=jacc(inst["seed"],g["file"]); ds=dir_sim(inst["seed"],g["file"])
        rows.append({"layer":lay,"jacc":j,"dir":ds,
                     "nc":g["file"] in nc,"sc":g["file"] in scd,
                     "seed":inst["seed"],"gold":g["file"],"proj":inst["project"]})

def report(rows, label):
    n=len(rows); ncr=sum(r["nc"] for r in rows); scr=sum(r["sc"] for r in rows)
    print(f"\n=== {label} (n={n}) ===")
    print(f"  no_card recall={ncr/n:.3f} ({ncr}/{n})  static_card recall={scr/n:.3f} ({scr}/{n})")
    # split by filename similarity buckets
    for lo,hi,name in [(0,0.0001,"jacc==0 (filename-DISSIMILAR)"),
                       (0.0001,0.5,"0<jacc<0.5"),(0.5,1.01,"jacc>=0.5 (very similar)")]:
        sub=[r for r in rows if lo<=r["jacc"]<hi]
        if not sub: continue
        ncs=sum(r["nc"] for r in sub); scs=sum(r["sc"] for r in sub)
        print(f"    [{name}] n={len(sub)}  no_card_recall={ncs/len(sub):.3f} ({ncs})  static_card_recall={scs/len(sub):.3f} ({scs})")
    # shared-dir==0 (different top dir) vs shared
    for cond,name in [(lambda r:r["dir"]==0,"diff top-dir"),(lambda r:r["dir"]>=1,"shared >=1 dir")]:
        sub=[r for r in rows if cond(r)]
        if not sub: continue
        ncs=sum(r["nc"] for r in sub)
        print(f"    [{name}] n={len(sub)}  no_card_recall={ncs/len(sub):.3f}")
    # of no_card RECALLED: how many filename-dissimilar (jacc==0) = true-capture candidate
    rec=[r for r in rows if r["nc"]]
    dissim=[r for r in rec if r["jacc"]==0]
    print(f"  of no_card-recalled {len(rec)}: jacc==0 (filename-INDEPENDENT) = {len(dissim)} ({len(dissim)/len(rec)*100:.1f}%)" if rec else "  none recalled")
    return rec,dissim

for lay in ["invisible_dynamic","invisible_namematch"]:
    sub=[r for r in rows if r["layer"]==lay]
    rec,dissim=report(sub,lay)
    print(f"  --- sample of no_card-recalled, filename-INDEPENDENT (jacc==0) {lay} ---")
    for r in dissim[:10]:
        print(f"     [{r['proj']}] {r['seed']}  ->  {r['gold']}  (jacc=0,dir={r['dir']})")
allinv=[r for r in rows if r["layer"].startswith("invisible")]
report(allinv,"ALL invisible")
json.dump(rows, open(os.path.join(T3,"pe7_filename_rows.json"),"w"))
