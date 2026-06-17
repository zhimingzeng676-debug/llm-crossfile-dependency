"""
M61 Task1 (CPU): build DEGRADED co-change cards simulating real deployment precision.
M59's 96% used card=gold (covers ~98% invisible gold). Real co-change cards differ:
  - coverage c: co-change mining finds only fraction c of true blind-spot edges
  - precision p: card contains false edges (co-change != dependency noise)
Build degraded cards over a sweep of (coverage, precision); score invisible recall vs
the FULL TRUE gold separately. Deterministic. co-change != dependency.
"""
import json, os, re, hashlib, glob
T3=r"D:\claude\59\pilot_devtruth\task3"; REPOS=r"D:\claude\59\pilot_devtruth\repos_hist"
def hk(s): return hashlib.md5(s.encode()).hexdigest()

# repo file universe per project (for false/noise edges)
allpy={}
for proj in os.listdir(REPOS):
    root=os.path.join(REPOS,proj)
    if not os.path.isdir(os.path.join(root,".git")): continue
    fs=[]
    for dp,_,fns in os.walk(root):
        if ".git" in dp.replace("\\","/").split("/"): continue
        for fn in fns:
            if fn.endswith(".py"): fs.append(os.path.relpath(os.path.join(dp,fn),root).replace("\\","/"))
    allpy[proj]=fs

insts=json.load(open(os.path.join(T3,"instances_cc.json")))
# sweep: coverage at p=1.0, plus noise combos
CONFIGS=[("cov100_p100",1.0,1.0),("cov70_p100",0.7,1.0),("cov50_p100",0.5,1.0),
         ("cov30_p100",0.3,1.0),("cov10_p100",0.1,1.0),
         ("cov50_p50",0.5,0.5),("cov30_p50",0.3,0.5),("cov50_p30",0.5,0.3)]

CARD_HDR=("Co-change history (files that historically change together with this file, "
          "from git history — may include runtime/dynamic coupling static analysis misses):\n")
def build(inst, c, p):
    seed=inst["seed"]; proj=inst["project"]
    gold=[g["file"] for g in inst["gold"]]
    others=[f for f in allpy.get(proj,[]) if f!=seed and f not in set(gold)]
    # coverage: keep deterministic c-fraction of gold partners
    gold_sorted=sorted(gold, key=lambda f:hk(seed+"cov"+f))
    keep=gold_sorted[:max(1,int(round(len(gold_sorted)*c)))] if gold_sorted else []
    # precision: add false edges so that precision among listed ~= p
    n_false=0
    if p<1.0 and keep:
        n_false=int(round(len(keep)*(1.0/p-1.0)))
    false=sorted(others, key=lambda f:hk(seed+"noise"+f))[:n_false]
    listed=keep+false
    listed=sorted(listed, key=lambda f:hk(seed+"order"+f))  # shuffle so model can't tell real from false
    return (CARD_HDR+", ".join(listed)) if listed else "(no co-change history)"

for inst in insts:
    inst["deg_cards"]={tag:build(inst,c,p) for tag,c,p in CONFIGS}
json.dump(insts, open(os.path.join(T3,"instances_decay.json"),"w"), indent=1)
# stats: avg listed, avg true-kept per config
print("built instances_decay.json; configs:")
for tag,c,p in CONFIGS:
    import statistics
    listed=[len(re.split(r",\s*", i["deg_cards"][tag].split("\n")[-1])) if "no co-change" not in i["deg_cards"][tag] else 0 for i in insts]
    print(f"  {tag:12} coverage={c} precision={p}  avg_listed={statistics.mean(listed):.1f}")
