"""
M52 Task1 mechanism instances: add filler_card (equal-length irrelevant prose,
NO file paths) and random_card (same format as static_card but random non-gold files)
to each invisible-subset instance. Tests context-budget vs content/anchoring.
co-change != dependency; no conclusion.
"""
import json, os, re, hashlib
T3=r"D:\claude\59\pilot_devtruth\task3"; REPOS=r"D:\claude\59\pilot_devtruth\repos_hist"
def hkey(s): return hashlib.md5(s.encode()).hexdigest()

# repo file lists
allpy={}
for proj in os.listdir(REPOS):
    root=os.path.join(REPOS,proj)
    if not os.path.isdir(os.path.join(root,".git")): continue
    fs=[]
    for dp,_,fns in os.walk(root):
        if ".git" in dp.replace("\\","/").split("/"): continue
        for fn in fns:
            if fn.endswith(".py"):
                fs.append(os.path.relpath(os.path.join(dp,fn),root).replace("\\","/"))
    allpy[proj]=fs

FILLER_SENT=("This section contains general background information about software "
"engineering conventions and is not specific to any particular module or file. ")
def make_filler(n):
    s=""
    while len(s)<n: s+=FILLER_SENT
    return s[:max(n,1)]

LABELS=[("imports","imports"),("imported_by","imported_by"),
        ("calls_into","calls_into"),("inherits_from","inherits_from")]
def parse_card_counts(card):
    cnt={}
    for line in card.splitlines():
        for key in ["imports","imported_by","calls_into","inherits_from"]:
            if line.startswith(key+":"):
                items=[x.strip() for x in line[len(key)+1:].split(",") if x.strip()]
                cnt[key]=len(items)
    return cnt
def make_random_card(proj, seed, goldset, real_card):
    cnt=parse_card_counts(real_card)
    if not cnt: return "(no static dependency edges found for this file)"
    files=[f for f in allpy.get(proj,[]) if f!=seed and f not in goldset]
    files=sorted(files,key=lambda f:hkey(seed+f))  # deterministic per-seed order
    out=[]; idx=0
    for key in ["imports","imported_by","calls_into","inherits_from"]:
        if key in cnt and cnt[key]>0:
            pick=files[idx:idx+cnt[key]]; idx+=cnt[key]
            if pick: out.append(f"{key}: "+", ".join(pick))
    return "\n".join(out) if out else "(no static dependency edges found for this file)"

insts=json.load(open(os.path.join(T3,"instances_ctrl_orig.json")))
out=[]
for i in insts:
    goldset={g["file"] for g in i["gold"]}
    card=i["static_card"]
    o={**i,
       "filler_card":make_filler(len(card)),
       "random_card":make_random_card(i["project"],i["seed"],goldset,card)}
    out.append(o)
json.dump(out,open(os.path.join(T3,"instances_mech.json"),"w"),indent=1)
# sanity
import statistics
print("instances:",len(out))
print("avg static_card len:",round(statistics.mean(len(i['static_card']) for i in out)))
print("avg filler len:",round(statistics.mean(len(i['filler_card']) for i in out)))
print("avg random_card len:",round(statistics.mean(len(i['random_card']) for i in out)))
ex=out[0]
print("\nexample static_card:\n",ex['static_card'][:200])
print("example random_card:\n",ex['random_card'][:200])
print("example filler:\n",ex['filler_card'][:120])
