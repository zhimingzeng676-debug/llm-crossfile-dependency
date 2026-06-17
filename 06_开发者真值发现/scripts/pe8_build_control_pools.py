"""
M51 control instances: rebuild candidate pools in 3 variants to rule out
  A (filename coincidence) and B (candidate-pool artifact) for no_card>static_card.
Variants (same seeds/gold/static_card, only candidate pool changes):
  orig         : original pool (reproduce baseline)
  clean        : gold + pure-random distractors (NO static neighbors, NO filename-similar)
  falsefriends : gold + filename-similar-but-NOT-cochanged decoys + random
Only instances with >=1 invisible gold edge (the finding's locus). evo (complete).
co-change != dependency; judge-independent; no conclusion.
"""
import json, os, re, glob, hashlib
T3=r"D:\claude\59\pilot_devtruth\task3"; REPOS=r"D:\claude\59\pilot_devtruth\repos_hist"
POOL_CAP=40
def toks(p):
    b=os.path.basename(p); b=b[:-3] if b.endswith(".py") else b
    return set(t for t in re.split(r"[_\W]+",b.lower()) if t)
def sim(a,b):
    ta,tb=toks(a),toks(b)
    return bool(ta&tb)  # shares >=1 filename token
def hkey(s): return hashlib.md5(s.encode()).hexdigest()

# all .py per project (repo-root-relative, posix)
allpy={}
for proj in os.listdir(REPOS):
    root=os.path.join(REPOS,proj)
    if not os.path.isdir(os.path.join(root,".git")): continue
    fs=[]
    for dp,_,fns in os.walk(root):
        if ".git" in dp.replace("\\","/").split("/"): continue
        for fn in fns:
            if fn.endswith(".py"):
                rel=os.path.relpath(os.path.join(dp,fn),root).replace("\\","/")
                fs.append(rel)
    allpy[proj]=set(fs)

insts=json.load(open(os.path.join(T3,"instances_evo_raw.json")))
inv=[i for i in insts if any(g["layer"].startswith("invisible") for g in i["gold"])]
print("evo instances with invisible gold:",len(inv),"of",len(insts))

def build(seed, gold, proj, mode):
    files=allpy.get(proj,set()); goldset=set(gold)
    pool=set(goldset)
    others=[f for f in files if f!=seed and f not in goldset]
    if mode=="clean":
        # pure random, exclude filename-similar to seed OR any gold
        cand=[f for f in others if not sim(f,seed) and not any(sim(f,g) for g in gold)]
        for f in sorted(cand,key=hkey):
            if len(pool)>=POOL_CAP: break
            pool.add(f)
    elif mode=="falsefriends":
        ff=[f for f in others if sim(f,seed)]      # filename-similar to seed, not gold
        for f in sorted(ff,key=hkey)[:15]: pool.add(f)
        for f in sorted(others,key=hkey):
            if len(pool)>=POOL_CAP: break
            pool.add(f)
    pool.discard(seed)
    return sorted(pool,key=hkey)

for mode in ["clean","falsefriends"]:
    out=[]
    for i in inv:
        gold_files=[g["file"] for g in i["gold"]]
        out.append({**i,"candidates":build(i["seed"],gold_files,i["project"],mode),"pool_mode":mode})
    json.dump(out,open(os.path.join(T3,f"instances_ctrl_{mode}.json"),"w"),indent=1)
    # report pool composition sanity
    avggold=sum(len([g for g in i['gold']]) for i in out)/len(out)
    print(f"{mode}: {len(out)} instances written, avg_gold={avggold:.1f}")
# orig = the invisible-subset with original pools
json.dump(inv,open(os.path.join(T3,"instances_ctrl_orig.json"),"w"),indent=1)
print("orig:",len(inv),"instances (original pools)")
# tag false-friend candidates count for precision metric later (decoys = pool ∩ filename-sim-to-seed, not gold)
