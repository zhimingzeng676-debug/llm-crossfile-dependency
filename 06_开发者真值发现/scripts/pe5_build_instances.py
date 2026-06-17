"""
Task3 Phase A (CPU): build seed-centric prediction instances.
Task = "given seed file X (changed), pick from a candidate pool which files the
developer co-changed with X". Score = recall against developer gold, split by
static visibility (visible / invisible). Judge-independent (gold from git co-change).

Builds for bug-fix (primary) and evo (secondary). De-noise ③ packaging files, two versions.
repo_parser UNMODIFIED. co-change != dependency.
"""
import os, sys, json, glob, hashlib, time, re
sys.path.insert(0,"D:/claude/49/src")
from repomind_lab.repo_parser import parse_repo
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,"out")
REPOS=os.path.join(ROOT,"repos_hist"); T3=os.path.join(ROOT,"task3"); os.makedirs(T3,exist_ok=True)
STAMP=time.strftime("%Y%m%d_%H%M%S")
LOG=open(os.path.join(T3,f"build_log_{STAMP}.txt"),"w",encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

POOL_CAP=40; SEED_MAXLEN=2500; GOLD_MAX=15

def is_noise(p):
    b=os.path.basename(p).lower()
    return b in ("setup.py","conftest.py","__init__.py","_version.py","version.py") or \
           "version" in b or b.endswith("/__init__.py")

def hkey(s):  # deterministic pseudo-shuffle key
    return hashlib.md5(s.encode()).hexdigest()

# ---- visibility lookup from pe4 ----
def load_pe4(glob_pat):
    d=json.load(open(sorted(glob.glob(os.path.join(OUT,glob_pat)))[-1]))
    m={}
    for r in d:
        if r.get("present"):
            m[(r["project"],frozenset((r["a"],r["b"])))]=r["bucket"]
    return m
bug_buck=load_pe4("pe4_bugfix_class_*.json")
evo_buck=load_pe4("pe4_evo_class_*.json")

def vis_layer(bucket):
    if bucket=="1_visible_precise": return "visible"
    if bucket=="2_namematch_gap": return "invisible_namematch"
    return "invisible_dynamic"  # 3_no_static_signal_*

# ---- per-project static analysis (parse once) ----
def analyze(repo):
    g=parse_repo(repo); files=set(g.files)
    imp=g.import_edges()
    # per-file neighbor sets + card material
    card={}  # file -> dict(imports/imported_by/calls/inherits sets)
    for f in files: card[f]={"imports":set(),"imported_by":set(),"calls":set(),"inherits":set()}
    for a,b in imp:
        card[a]["imports"].add(b); card[b]["imported_by"].add(a)
    # resolved calls
    for f in g.functions:
        F=f.file
        for c in f.calls:
            rn,df=g.resolve_symbol(F,c)
            if df and df!=F and df in files: card[F]["calls"].add(df)
    for c in g.classes:
        for bse in c.bases:
            rn,df=g.resolve_symbol(c.file,bse)
            if df and df!=c.file and df in files: card[c.file]["inherits"].add(df)
    # PREC adjacency (undirected) per file
    prec={f:set() for f in files}
    for f in files:
        for k in ("imports","imported_by","calls","inherits"):
            for o in card[f][k]:
                prec[f].add(o); prec[o].add(f)
    return files,card,prec

def read_src(repo,rel):
    try: return open(os.path.join(repo,rel),encoding="utf-8",errors="replace").read()
    except Exception: return None

def card_text(c):
    parts=[]
    if c["imports"]: parts.append("imports: "+", ".join(sorted(c["imports"])[:15]))
    if c["imported_by"]: parts.append("imported_by: "+", ".join(sorted(c["imported_by"])[:15]))
    if c["calls"]: parts.append("calls_into: "+", ".join(sorted(c["calls"])[:15]))
    if c["inherits"]: parts.append("inherits_from: "+", ".join(sorted(c["inherits"])[:10]))
    return "\n".join(parts) if parts else "(no static dependency edges found for this file)"

def build_pool(seed, gold_present, prec_nb, all_files):
    pool=set(gold_present)
    # static neighbors as distractors (test over-reliance on static)
    for n in sorted(prec_nb)[:15]: pool.add(n)
    # filename-token-similar distractors
    stem=os.path.basename(seed)[:-3].lower()
    toks=set(re.split(r"[_\W]+",stem))-{""}
    sims=[f for f in all_files if f!=seed and (set(re.split(r"[_\W]+",os.path.basename(f)[:-3].lower()))&toks)]
    for f in sorted(sims, key=hkey)[:10]: pool.add(f)
    # fill with deterministic "random" distractors
    for f in sorted(all_files, key=hkey):
        if len(pool)>=POOL_CAP: break
        pool.add(f)
    pool.discard(seed)
    return sorted(pool, key=hkey)

def make_instances(seeds_gold, project, repo, files, card, prec, buck, denoise):
    """seeds_gold: dict seed -> set(gold files). returns list of instances."""
    inst=[]
    all_files=sorted(files)
    for seed, gold in seeds_gold.items():
        if seed not in files: continue
        if denoise and is_noise(seed): continue
        gp=[y for y in gold if y in files and (not denoise or not is_noise(y))]
        if not gp: continue
        if len(gp)>GOLD_MAX:  # cap, record
            gp=sorted(gp, key=hkey)[:GOLD_MAX]
        src=read_src(repo,seed)
        if src is None: continue
        gold_lab=[]
        for y in gp:
            b=buck.get((project,frozenset((seed,y))))
            if b is None:  # not in pe4 (e.g., evo seed-neighbor not a primary edge dir) -> compute layer via prec
                lay="visible" if y in prec.get(seed,set()) else "invisible_unknown"
            else: lay=vis_layer(b)
            gold_lab.append({"file":y,"layer":lay})
        inst.append({
            "project":project,"seed":seed,
            "seed_code":src[:SEED_MAXLEN],
            "candidates":build_pool(seed,gp,prec.get(seed,set()),all_files),
            "static_card":card_text(card[seed]),
            "gold":gold_lab,
        })
    return inst

# ---- assemble seed->gold ----
recs=json.load(open(sorted(glob.glob(os.path.join(OUT,"p1_records_*.json")))[-1]))
bug_seedgold={}  # project -> {seed -> set(gold)}
for r in recs:
    if r["n_src_py"]>=2:
        fs=r["src_py_files"]
        for s in fs:
            bug_seedgold.setdefault(r["project"],{}).setdefault(s,set()).update(x for x in fs if x!=s)
evo_edges=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
evo_seedgold={}
for e in evo_edges:
    p=e["project"]
    evo_seedgold.setdefault(p,{}).setdefault(e["a"],set()).add(e["b"])
    evo_seedgold.setdefault(p,{}).setdefault(e["b"],set()).add(e["a"])

projects=sorted(set(bug_seedgold)|set(evo_seedgold))
for denoise in (False, True):
    tag="denoised" if denoise else "raw"
    bug_inst=[]; evo_inst=[]
    for p in projects:
        repo=os.path.join(REPOS,p)
        if not os.path.isdir(repo): continue
        if p not in getattr(make_instances,"_cache",{}):
            pass
        try:
            files,card,prec=analyze(repo)
        except Exception as ex:
            log(f"[FAIL parse] {p}: {ex!r}"); continue
        if p in bug_seedgold:
            bug_inst+=make_instances(bug_seedgold[p],p,repo,files,card,prec,bug_buck,denoise)
        if p in evo_seedgold:
            evo_inst+=make_instances(evo_seedgold[p],p,repo,files,card,prec,evo_buck,denoise)
        log(f"  [{tag}] {p}: bug_inst+={sum(1 for i in bug_inst if i['project']==p)} evo_inst+={sum(1 for i in evo_inst if i['project']==p)}")
    json.dump(bug_inst,open(os.path.join(T3,f"instances_bugfix_{tag}.json"),"w"),indent=1)
    json.dump(evo_inst,open(os.path.join(T3,f"instances_evo_{tag}.json"),"w"),indent=1)
    def layct(inst):
        from collections import Counter
        c=Counter(g["layer"] for i in inst for g in i["gold"])
        return dict(c)
    log(f"[{tag}] BUGFIX instances={len(bug_inst)} gold_edges_by_layer={layct(bug_inst)}")
    log(f"[{tag}] EVO    instances={len(evo_inst)} gold_edges_by_layer={layct(evo_inst)}")
log("[done] pe5", T3); LOG.close()
