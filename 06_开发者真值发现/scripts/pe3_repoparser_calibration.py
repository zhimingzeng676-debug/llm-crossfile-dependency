"""
Phase E3 (CPU, judge-independent): recompute static visibility of developer
co-change edges using the PROJECT'S OWN repo_parser (tree-sitter), which captures
import + call + inheritance edges over the WHOLE repo at HEAD. This calibrates the
load-bearing blind-spot number that the import-level proxy may have overstated.

repo_parser is used UNMODIFIED (imported from D:/claude/49/src). co-change != dependency.
Calibers: import-only / +call / +call+inherit (authoritative). Multi-caliber all reported.
Edges whose file is absent at HEAD are flagged absent_at_head and NOT counted in rates.
No conclusions drawn.
"""
import os, sys, json, glob, time
sys.path.insert(0, "D:/claude/49/src")
from repomind_lab.repo_parser import parse_repo

ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,"out")
REPOS=os.path.join(ROOT,"repos_hist")
STAMP=time.strftime("%Y%m%d_%H%M%S")
LOG=open(os.path.join(OUT,f"pe3_log_{STAMP}.txt"),"w",encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

AMBIG_CAP=5  # skip call/class edges whose name maps to > CAP files (unreliable; reported)

def build_adj(repo):
    g=parse_repo(repo)
    files=set(g.files)
    imp=set()
    for a,b in g.import_edges():
        if a!=b: imp.add(frozenset((a,b)))
    # name -> files
    fn2f={}; cl2f={}
    for f in g.functions: fn2f.setdefault(f.name,set()).add(f.file)
    for c in g.classes:   cl2f.setdefault(c.name,set()).add(c.file)
    call=set(); skipped_call=0
    for cn,ce in g.call_edges():
        fa,fb=fn2f.get(cn,set()),fn2f.get(ce,set())
        if len(fa)>AMBIG_CAP or len(fb)>AMBIG_CAP: skipped_call+=1; continue
        for x in fa:
            for y in fb:
                if x!=y: call.add(frozenset((x,y)))
    cls=set(); skipped_cls=0
    for sub,base in g.class_edges():
        fa,fb=cl2f.get(sub,set()),cl2f.get(base,set())
        if len(fa)>AMBIG_CAP or len(fb)>AMBIG_CAP: skipped_cls+=1; continue
        for x in fa:
            for y in fb:
                if x!=y: cls.add(frozenset((x,y)))
    return files,imp,call,cls,{"n_files":len(files),"n_func":len(g.functions),
            "n_class":len(g.classes),"n_import_edges":len(imp),
            "n_call_file_pairs":len(call),"n_class_file_pairs":len(cls),
            "skipped_ambig_call":skipped_call,"skipped_ambig_class":skipped_cls}

def classify_set(edges, adjs):
    """edges: list of {project,a,b,...}. adjs: proj-> (files,imp,call,cls)."""
    out=[]
    for e in edges:
        p=e["project"]
        if p not in adjs:
            out.append({**e,"present":False,"reason":"repo_not_parsed"}); continue
        files,imp,call,cls=adjs[p]
        if e["a"] not in files or e["b"] not in files:
            out.append({**e,"present":False,"reason":"absent_at_head"}); continue
        key=frozenset((e["a"],e["b"]))
        vi=key in imp
        vc=vi or (key in call)
        vf=vc or (key in cls)
        out.append({**e,"present":True,"vis_import":vi,"vis_call":vc,"vis_full":vf})
    return out

def rates(classified):
    pres=[r for r in classified if r["present"]]
    n=len(pres)
    if not n: return {"n_present":0}
    def vr(k): return round(sum(1 for r in pres if r[k])/n,4)
    return {"n_total":len(classified),"n_present":n,
            "n_absent":sum(1 for r in classified if not r["present"]),
            "visible":{"import":vr("vis_import"),"call":vr("vis_call"),"full":vr("vis_full")},
            "invisible":{"import":round(1-vr("vis_import"),4),
                         "call":round(1-vr("vis_call"),4),
                         "full":round(1-vr("vis_full"),4)}}

# ---- load edge sets ----
bug_edges=json.load(open(sorted(glob.glob(os.path.join(OUT,"p1_edges_untangled_*.json")))[-1]))
evo_edges=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
projects=sorted({e["project"] for e in bug_edges}|{e["project"] for e in evo_edges})

# ---- parse each repo once ----
adjs={}; pstats={}
for p in projects:
    repo=os.path.join(REPOS,p)
    if not os.path.isdir(repo): log(f"[skip] {p} no repo"); continue
    log(f"[parse] {p} ...")
    try:
        files,imp,call,cls,st=build_adj(repo)
        adjs[p]=(files,imp,call,cls); pstats[p]=st
        log(f"  {p}: files={st['n_files']} imp_edges={st['n_import_edges']} "
            f"call_pairs={st['n_call_file_pairs']} class_pairs={st['n_class_file_pairs']} "
            f"(skipped ambig call={st['skipped_ambig_call']} class={st['skipped_ambig_class']})")
    except Exception as ex:
        log(f"[FAIL parse] {p}: {ex!r}")

bug_cls=classify_set(bug_edges,adjs)
evo_cls=classify_set(evo_edges,adjs)
json.dump(bug_cls,open(os.path.join(OUT,f"pe3_bugfix_class_{STAMP}.json"),"w"),indent=1)
json.dump(evo_cls,open(os.path.join(OUT,f"pe3_evo_class_{STAMP}.json"),"w"),indent=1)

result={"stamp":STAMP,"ambig_cap":AMBIG_CAP,
        "bugfix_repoparser":rates(bug_cls),
        "evo_repoparser":rates(evo_cls),
        "per_project_parse_stats":pstats,
        "note":"HEAD-based. bug-fix edges originally measured at fixed_commit; "
               "here re-judged at HEAD (files moved/renamed since become absent_at_head)."}
json.dump(result,open(os.path.join(OUT,f"pe3_summary_{STAMP}.json"),"w"),indent=1)

log("\n=== repo_parser CALIBRATION (HEAD; import / +call / +call+inherit) ===")
for label,r in [("BUG-FIX edges",result["bugfix_repoparser"]),("EVO edges",result["evo_repoparser"])]:
    if r.get("n_present"):
        log(f"  {label}: present={r['n_present']}/{r['n_total']} (absent_at_head={r['n_absent']})")
        log(f"    INVISIBLE  import={r['invisible']['import']}  +call={r['invisible']['call']}  +call+inherit(FULL)={r['invisible']['full']}")
        log(f"    VISIBLE    import={r['visible']['import']}  +call={r['visible']['call']}  FULL={r['visible']['full']}")
log("\n  COMPARE vs import-proxy (Phase2/E2):")
log("    bug-fix proxy invisible med=0.194 ; evo proxy invisible med=0.284")
log("[done] pe3", OUT); LOG.close()
