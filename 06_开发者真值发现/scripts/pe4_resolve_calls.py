"""
Phase E4 (CPU, judge-independent): cap-FREE stable blind-spot via file-level call
disambiguation using repo_parser's OWN resolve_symbol alias chain (M3-A).

For each call `c` inside a function in file F, resolve_symbol(F, c) follows the
import/alias chain to the EXACT defining file (not "every file with a function
named c"). This removes the ambiguity-cap dependency entirely.

repo_parser is used UNMODIFIED. co-change != dependency. No conclusions.

Three buckets for each present co-change edge (A,B):
  1. visible_precise  : {A,B} linked by import OR resolved-call OR resolved-inherit
  2. namematch_gap    : NOT precise-visible, but a name-level def/call link exists
                        between A,B (resolve couldn't bind: method dispatch / re-export
                        / missing import) -> theoretically static-analyzable
  3. no_static_signal : no import, no resolved/​name call, no inherit link at all
                        (+ dynamic-marker subflag) -> candidate truly-dynamic/runtime
Stable blind-spot = 1 - |visible_precise|/n_present  (cap-free).
"""
import os, sys, json, glob, time, re
sys.path.insert(0,"D:/claude/49/src")
from repomind_lab.repo_parser import parse_repo
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,"out")
REPOS=os.path.join(ROOT,"repos_hist")
STAMP=time.strftime("%Y%m%d_%H%M%S")
LOG=open(os.path.join(OUT,f"pe4_log_{STAMP}.txt"),"w",encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

DYN=re.compile(r"__import__|importlib|getattr\(|setattr\(|globals\(\)|register|plugin|entry_point|exec\(|eval\(|__subclasses__|importlib")

def analyze_repo(repo):
    g=parse_repo(repo)
    files=set(g.files)
    # import adjacency (file level)
    imp=set(frozenset((a,b)) for a,b in g.import_edges() if a!=b)
    # precise call adjacency via resolve_symbol
    prec_call=set(); n_call_resolved=0; n_call_total=0
    for f in g.functions:
        F=f.file
        for c in f.calls:
            n_call_total+=1
            rname,dfile=g.resolve_symbol(F,c)
            if dfile and dfile!=F and dfile in files:
                prec_call.add(frozenset((F,dfile))); n_call_resolved+=1
    # precise inherit adjacency via resolve_symbol on base names
    prec_inh=set()
    for c in g.classes:
        for b in c.bases:
            rname,dfile=g.resolve_symbol(c.file,b)
            if dfile and dfile!=c.file and dfile in files:
                prec_inh.add(frozenset((c.file,dfile)))
    # name-level maps (for namematch_gap bucket)
    defs_in={}   # file -> set(func+class names defined)
    calls_in={}  # file -> set(callee names)
    for f in g.functions:
        defs_in.setdefault(f.file,set()).add(f.name)
        calls_in.setdefault(f.file,set()).update(f.calls)
    for c in g.classes:
        defs_in.setdefault(c.file,set()).add(c.name)
    class_bases_in={}  # file -> set(base names used)
    for c in g.classes:
        class_bases_in.setdefault(c.file,set()).update(c.bases)
    PREC=imp|prec_call|prec_inh
    stats={"n_files":len(files),"n_import_edges":len(imp),
           "n_prec_call_pairs":len(prec_call),"n_prec_inh_pairs":len(prec_inh),
           "calls_total":n_call_total,"calls_resolved_xfile":n_call_resolved}
    return files,PREC,defs_in,calls_in,class_bases_in,stats

def namematch(A,B,defs_in,calls_in,class_bases_in):
    """does a name-level call/inherit link exist between A and B (either dir)?"""
    cA,cB=calls_in.get(A,set()),calls_in.get(B,set())
    dA,dB=defs_in.get(A,set()),defs_in.get(B,set())
    if cA & dB or cB & dA: return True
    bA,bB=class_bases_in.get(A,set()),class_bases_in.get(B,set())
    if bA & dB or bB & dA: return True
    return False

def read_file(repo,rel):
    p=os.path.join(repo,rel)
    try: return open(p,encoding="utf-8",errors="replace").read()
    except Exception: return ""

def classify(edges,repos_data):
    out=[]
    for e in edges:
        p=e["project"]
        if p not in repos_data:
            out.append({**e,"present":False,"reason":"repo_not_parsed"}); continue
        files,PREC,defs_in,calls_in,cbases,_=repos_data[p]
        A,B=e["a"],e["b"]
        if A not in files or B not in files:
            out.append({**e,"present":False,"reason":"absent_at_head"}); continue
        key=frozenset((A,B))
        if key in PREC:
            bucket="1_visible_precise"
        elif namematch(A,B,defs_in,calls_in,cbases):
            bucket="2_namematch_gap"
        else:
            txt=read_file(os.path.join(REPOS,p),A)+"\n"+read_file(os.path.join(REPOS,p),B)
            bucket="3_no_static_signal_dynamic" if DYN.search(txt) else "3_no_static_signal_plain"
        out.append({**e,"present":True,"bucket":bucket})
    return out

bug=json.load(open(sorted(glob.glob(os.path.join(OUT,"p1_edges_untangled_*.json")))[-1]))
evo=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
projects=sorted({e["project"] for e in bug}|{e["project"] for e in evo})

repos_data={}; pstats={}
for p in projects:
    repo=os.path.join(REPOS,p)
    if not os.path.isdir(repo): continue
    log(f"[analyze] {p}")
    try:
        files,PREC,defs_in,calls_in,cbases,st=analyze_repo(repo)
        repos_data[p]=(files,PREC,defs_in,calls_in,cbases,st); pstats[p]=st
        log(f"  {p}: files={st['n_files']} imp={st['n_import_edges']} "
            f"prec_call={st['n_prec_call_pairs']} prec_inh={st['n_prec_inh_pairs']} "
            f"calls_resolved_xfile={st['calls_resolved_xfile']}/{st['calls_total']}")
    except Exception as ex:
        log(f"[FAIL] {p}: {ex!r}")

def summarize(cls,label):
    pres=[r for r in cls if r["present"]]
    n=len(pres)
    from collections import Counter
    b=Counter(r["bucket"] for r in pres)
    vis=b["1_visible_precise"]
    blind=round(1-vis/n,4) if n else None
    s={"label":label,"n_total":len(cls),"n_present":n,
       "n_absent":sum(1 for r in cls if not r["present"]),
       "stable_blindspot_precise":blind,
       "buckets":{k:b[k] for k in sorted(b)},
       "bucket_frac":{k:round(b[k]/n,4) for k in sorted(b)} if n else {}}
    return s

bug_cls=classify(bug,repos_data); evo_cls=classify(evo,repos_data)
json.dump(bug_cls,open(os.path.join(OUT,f"pe4_bugfix_class_{STAMP}.json"),"w"),indent=1)
json.dump(evo_cls,open(os.path.join(OUT,f"pe4_evo_class_{STAMP}.json"),"w"),indent=1)
sb=summarize(bug_cls,"bugfix"); se=summarize(evo_cls,"evo")
json.dump({"stamp":STAMP,"bugfix":sb,"evo":se,"parse_stats":pstats},
          open(os.path.join(OUT,f"pe4_summary_{STAMP}.json"),"w"),indent=1)

log("\n=== E4 CAP-FREE STABLE BLIND-SPOT (resolve_symbol file-level call disambiguation) ===")
for s in (sb,se):
    log(f"\n  {s['label'].upper()}: present={s['n_present']}/{s['n_total']} (absent_at_head={s['n_absent']})")
    log(f"    STABLE BLIND-SPOT (precise import+call+inherit) = {s['stable_blindspot_precise']}")
    log(f"    three-class breakdown (frac of present):")
    for k,v in s['bucket_frac'].items():
        log(f"      {k:34} {v}")
log("\n  (compare: cap-sweep gave 5%-45% bugfix / 13%-47% evo; import-only 54%/61%)")
log("[done] pe4", OUT); LOG.close()
