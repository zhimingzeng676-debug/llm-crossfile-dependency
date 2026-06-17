"""
Phase E2 (CPU, judge-independent): static visibility of evolutionary-coupling edges.
Reads file content at HEAD from the partial-clone repos (git show HEAD:path),
same import-level multi-caliber classifier as p2. Same HONEST LIMITATIONS as p2
(import-level direct-edge proxy; not the project's repo_parser).
"""
import os, sys, json, glob, ast, re, time, subprocess
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,"out")
REPOS=os.path.join(ROOT,"repos_hist")
STAMP=sys.argv[1] if len(sys.argv)>1 else time.strftime("%Y%m%d_%H%M%S")
LOG=open(os.path.join(OUT,f"pe2_log_{STAMP}.txt"),"w",encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

edges=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1],encoding="utf-8"))

_head={}
def head(repo):
    if repo not in _head:
        p=subprocess.run(["git","-C",repo,"rev-parse","HEAD"],capture_output=True,text=True)
        _head[repo]=p.stdout.strip() if p.returncode==0 else None
    return _head[repo]
def show(repo,path):
    p=subprocess.run(["git","-C",repo,"show",f"HEAD:{path}"],capture_output=True,text=True,errors="replace")
    return p.stdout if p.returncode==0 else None

def path_to_module(path):
    p=path[:-3] if path.endswith(".py") else path
    parts=p.split("/")
    if parts and parts[-1]=="__init__": parts=parts[:-1]
    return ".".join(parts),parts
def package_parts_of(path):
    p=path[:-3] if path.endswith(".py") else path
    parts=p.split("/")
    return parts[:-1] if not (parts and parts[-1]=="__init__") else parts[:-1]
def imports_of(src,file_path):
    mods=set()
    if src is None: return mods,False
    try: tree=ast.parse(src)
    except Exception: return mods,True
    pkg=package_parts_of(file_path)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for n in node.names: mods.add(n.name)
        elif isinstance(node,ast.ImportFrom):
            level=node.level or 0; base=node.module or ""
            if level==0:
                if base:
                    mods.add(base)
                    for n in node.names: mods.add(base+"."+n.name)
            else:
                up=pkg[:len(pkg)-(level-1)] if (level-1)<=len(pkg) else []
                root=".".join(up); full=(root+"."+base) if (root and base) else (base or root)
                if full:
                    mods.add(full)
                    for n in node.names: mods.add(full+"."+n.name)
    return mods,False
def stem(p):
    b=os.path.basename(p); return b[:-3] if b.endswith(".py") else b

def classify(e):
    proj=e["project"]; repo=os.path.join(REPOS,proj); A,B=e["a"],e["b"]
    srcA=show(repo,A); srcB=show(repo,B)
    fetched=(srcA is not None) and (srcB is not None)
    modA,_=path_to_module(A); modB,_=path_to_module(B)
    impA,_=imports_of(srcA,A); impB,_=imports_of(srcB,B)
    def hit(imps,tmod):
        strict=tmod in imps; med=strict
        for m in imps:
            if m==tmod or tmod.startswith(m+".") or m.startswith(tmod+"."): med=True
        return strict,med
    sA,mA=hit(impA,modB); sB,mB=hit(impB,modA)
    strict=sA or sB; med=mA or mB
    loose=med
    if not loose and srcA and re.search(r"\b"+re.escape(stem(B))+r"\b",srcA): loose=True
    if not loose and srcB and re.search(r"\b"+re.escape(stem(A))+r"\b",srcB): loose=True
    sub=None
    if not med:
        t=(srcA or "")+"\n"+(srcB or "")
        if not fetched: sub="file_absent_at_head"
        elif re.search(r"__import__|importlib|getattr\(|globals\(\)|register|plugin|entry_point|exec\(|eval\(",t): sub="dynamic_or_registry_hint"
        elif A.endswith("__init__.py") or B.endswith("__init__.py"): sub="package_init_coupling"
        elif os.path.dirname(A)==os.path.dirname(B): sub="same_dir_sibling_no_static_edge"
        else: sub="cross_dir_no_static_edge"
    return {**e,"fetched":fetched,"strict":strict,"med":med,"loose":loose,"invisible_subtype":sub}

log(f"[start] pe2 {STAMP} edges={len(edges)}")
res=[]
for i,e in enumerate(edges):
    res.append(classify(e))
    if (i+1)%200==0: log(f"  {i+1}/{len(edges)}")
json.dump(res,open(os.path.join(OUT,f"pe2_edge_class_{STAMP}.json"),"w"),indent=1)

fetched=[r for r in res if r["fetched"]]; n=len(fetched)
def rate(k): return round(sum(1 for r in fetched if r[k])/n,4) if n else None
sub={}
for r in fetched:
    if not r["med"]: sub[r["invisible_subtype"]]=sub.get(r["invisible_subtype"],0)+1
summary={"stamp":STAMP,"n_edges":len(res),"n_fetched":n,"n_absent":len(res)-n,
    "visible":{"strict":rate("strict"),"med":rate("med"),"loose":rate("loose")},
    "invisible":{"strict":round(1-rate("strict"),4) if n else None,
                 "med":round(1-rate("med"),4) if n else None,
                 "loose":round(1-rate("loose"),4) if n else None},
    "invisible_subtypes_med":dict(sorted(sub.items(),key=lambda x:-x[1]))}
json.dump(summary,open(os.path.join(OUT,f"pe2_summary_{STAMP}.json"),"w"),indent=1)
log("\n=== EVO-EDGE STATIC VISIBILITY (import-level, multi-caliber) ===")
log(f"  edges fetched: {n}/{len(res)} (absent_at_head={len(res)-n})")
log(f"  VISIBLE strict={summary['visible']['strict']} med={summary['visible']['med']} loose={summary['visible']['loose']}")
log(f"  INVISIBLE strict={summary['invisible']['strict']} med={summary['invisible']['med']} loose={summary['invisible']['loose']}")
log("  invisible subtypes (med):", summary["invisible_subtypes_med"])
log("[done] pe2", OUT); LOG.close()
