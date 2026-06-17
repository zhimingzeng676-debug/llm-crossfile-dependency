"""
M56 Task2 (CPU part): (a) verify judge's in-pool-rate confound, (b) dose-response
by pool_static from existing scores_mech, (c) build random_in_pool instances (random
files but IN the candidate pool, in-pool rate comparable to static_card).
No new GPU here; random_in_pool scoring is a separate GPU run.
co-change != dependency.
"""
import json, os, re, hashlib, math
T3=r"D:\claude\59\pilot_devtruth\task3"
def hkey(s): return hashlib.md5(s.encode()).hexdigest()

insts=json.load(open(os.path.join(T3,"instances_mech.json")))
sc=json.load(open(os.path.join(T3,"scores_mech.json")))
pred={(r["project"],r["seed"]):r["preds"] for r in sc["results"] if not r.get("_err")}

def card_files(card):
    fs=set()
    for line in (card or "").splitlines():
        for key in ["imports","imported_by","calls_into","inherits_from"]:
            if line.startswith(key+":"):
                for x in line[len(key)+1:].split(","):
                    x=x.strip()
                    if x and x.endswith(".py"): fs.add(x)
    return fs

# (a) in-pool rate: fraction of card-listed files that are in the candidate pool
def inpool_rate(field):
    num=den=0
    for i in insts:
        cset=set(i["candidates"]); cf=card_files(i.get(field,""))
        den+=len(cf); num+=len(cf & cset)
    return num/den if den else None
print("=== (a) in-pool rate of card-listed files (verify judge confound) ===")
print(f"  static_card: {inpool_rate('static_card'):.3f}")
print(f"  random_card: {inpool_rate('random_card'):.3f}  (judge: ~0.115)")

# static neighbors of seed = static_card files; pool_static = |candidates ∩ static_card files|
for i in insts:
    i["_pool_static"]=len(set(i["candidates"]) & card_files(i["static_card"]))

# (b) dose-response: lever (no_card vs static_card) stratified by pool_static, invisible
def lever(rows):
    n=len(rows)
    if not n: return None
    nc=sum(r["nc"] for r in rows)/n; st=sum(r["st"] for r in rows)/n
    b01=sum(1 for r in rows if r["st"] and not r["nc"]); b10=sum(1 for r in rows if r["nc"] and not r["st"])
    m=b01+b10; k=min(b01,b10); p=min(1.0,2*sum(math.comb(m,i) for i in range(k+1))/(2**m)) if m else None
    return n,nc,st,nc-st,b10,b01,p
recs=[]
for i in insts:
    key=(i["project"],i["seed"])
    if key not in pred: continue
    nc=set(pred[key].get("no_card",[])); st=set(pred[key].get("static_card",[]))
    for g in i["gold"]:
        if not g["layer"].startswith("invisible"): continue
        recs.append({"ps":i["_pool_static"],"nc":g["file"] in nc,"st":g["file"] in st})
print("\n=== (b) dose-response: lever by pool_static (invisible all) ===")
for label,sel in [("pool_static==0",lambda r:r["ps"]==0),("pool_static>=1",lambda r:r["ps"]>=1),
                  ("pool_static>=3",lambda r:r["ps"]>=3)]:
    rr=[r for r in recs if sel(r)]; L=lever(rr)
    if L: print(f"  {label:16} n={L[0]:4} no_card={L[1]:.3f} static={L[2]:.3f} Δ={L[3]:+.3f} (nc-only={L[4]} st-only={L[5]} p={L[6]:.3g})")
    else: print(f"  {label}: n=0")

# (c) build random_in_pool: random files IN pool, NOT gold, NOT static-neighbor; same count as static_card
out=[]
for i in insts:
    cset=[c for c in i["candidates"]]
    gold={g["file"] for g in i["gold"]}; stn=card_files(i["static_card"])
    n_entries=len(stn) if stn else 3
    cand=[c for c in cset if c not in gold and c not in stn]
    cand=sorted(cand,key=lambda f:hkey(i["seed"]+"rip"+f))[:max(n_entries,1)]
    # format like a static card (single 'imports:' line is fine; framing identical via scorer)
    rip = ("imports: "+", ".join(cand)) if cand else "(no static dependency edges found for this file)"
    out.append({**i,"random_in_pool":rip})
json.dump(out,open(os.path.join(T3,"instances_mech_inpool.json"),"w"),indent=1)
# report in-pool rate of the new random_in_pool card
num=den=0
for i in out:
    cf=card_files(i["random_in_pool"]); den+=len(cf); num+=len(cf & set(i["candidates"]))
print(f"\n=== (c) built instances_mech_inpool.json; random_in_pool in-pool rate={num/den:.3f} (target ~static 0.95) ===")
