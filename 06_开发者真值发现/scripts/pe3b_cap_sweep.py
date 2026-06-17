"""
Phase E3b (CPU): ambiguity-cap sensitivity sweep for the load-bearing blind-spot.
Parse each repo ONCE with repo_parser, cache raw edges + name->file maps, then build
file-level adjacency at multiple ambiguity caps and report invisible (FULL caliber).
Measurement only; no conclusions.
"""
import os, sys, json, glob, time
sys.path.insert(0,"D:/claude/49/src")
from repomind_lab.repo_parser import parse_repo
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,"out")
REPOS=os.path.join(ROOT,"repos_hist")
STAMP=time.strftime("%Y%m%d_%H%M%S")
LOG=open(os.path.join(OUT,f"pe3b_log_{STAMP}.txt"),"w",encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

CAPS=[1,3,5,10,10**9]
bug=json.load(open(sorted(glob.glob(os.path.join(OUT,"p1_edges_untangled_*.json")))[-1]))
evo=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
projects=sorted({e["project"] for e in bug}|{e["project"] for e in evo})

cache={}  # proj -> (files,imp_set, call_name_pairs, class_name_pairs, fn2f, cl2f)
for p in projects:
    repo=os.path.join(REPOS,p)
    if not os.path.isdir(repo): continue
    log(f"[parse] {p}")
    g=parse_repo(repo)
    imp=set(frozenset((a,b)) for a,b in g.import_edges() if a!=b)
    fn2f={}; cl2f={}
    for f in g.functions: fn2f.setdefault(f.name,set()).add(f.file)
    for c in g.classes:   cl2f.setdefault(c.name,set()).add(c.file)
    cache[p]=(set(g.files),imp,g.call_edges(),g.class_edges(),fn2f,cl2f)

def adj_at_cap(p,cap):
    files,imp,calls,classes,fn2f,cl2f=cache[p]
    A=set(imp)
    for cn,ce in calls:
        fa,fb=fn2f.get(cn,set()),fn2f.get(ce,set())
        if len(fa)>cap or len(fb)>cap: continue
        for x in fa:
            for y in fb:
                if x!=y: A.add(frozenset((x,y)))
    for sub,base in classes:
        fa,fb=cl2f.get(sub,set()),cl2f.get(base,set())
        if len(fa)>cap or len(fb)>cap: continue
        for x in fa:
            for y in fb:
                if x!=y: A.add(frozenset((x,y)))
    return files,A

def invis_full(edges,cap):
    present=0; vis=0
    for e in edges:
        p=e["project"]
        if p not in cache: continue
        files,A=ADJ[(p,cap)]
        if e["a"] not in files or e["b"] not in files: continue
        present+=1
        if frozenset((e["a"],e["b"])) in A: vis+=1
    return present, (round(1-vis/present,4) if present else None)

ADJ={}
for p in cache:
    for cap in CAPS:
        ADJ[(p,cap)]=adj_at_cap(p,cap)

res={"stamp":STAMP,"caps":CAPS,"bugfix":{},"evo":{}}
log("\n=== AMBIG-CAP SWEEP (invisible, FULL caliber import+call+inherit) ===")
log(f"{'cap':>6} {'bugfix_inv':>12} {'bugfix_n':>9} {'evo_inv':>10} {'evo_n':>7}")
for cap in CAPS:
    nb,ib=invis_full(bug,cap); ne,ie=invis_full(evo,cap)
    capname="inf" if cap>=10**9 else str(cap)
    res["bugfix"][capname]={"n_present":nb,"invisible_full":ib}
    res["evo"][capname]={"n_present":ne,"invisible_full":ie}
    log(f"{capname:>6} {ib:>12} {nb:>9} {ie:>10} {ne:>7}")
json.dump(res,open(os.path.join(OUT,f"pe3b_capsweep_{STAMP}.json"),"w"),indent=1)
log("[done] pe3b", OUT); LOG.close()
