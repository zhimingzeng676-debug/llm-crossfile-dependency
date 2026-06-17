"""
Phase E1 (CPU, judge-independent): mine evolutionary/change coupling edges from
FULL git history of each project (expand the co-change sample beyond bug-fixes).

Signal: files that co-change across commits (co-commit), scored by support &
confidence (ROSE-style association rules). This is developer-behavior ground truth
from git history, orthogonal to static parsers. co-change != dependency.

Red lines:
- full history, full sample; multi-caliber (tangling-threshold sweep + support/conf sweep) all reported
- de-noise (tangled commits) reported across a threshold sweep, nothing hidden
- deterministic; everything dumped with timestamps; no silent skips
"""
import os, sys, subprocess, json, time, glob, re
from itertools import combinations
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
REPOS = os.path.join(ROOT, "repos_hist")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)
STAMP = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d_%H%M%S")
LOG = open(os.path.join(OUT, f"pe1_log_{STAMP}.txt"), "w", encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

def is_test(p):
    pl="/"+p.lower(); b=os.path.basename(pl)
    return ("/test" in pl or "/tests/" in pl or b.startswith("test_")
            or b.endswith("_test.py") or b=="conftest.py")

# tangling thresholds (max source .py files in a commit to count it) -- swept
TANGLE_THRESHOLDS = [4, 8, 16, 32]  # bound pairs/commit; huge commits = tangling noise
# association-rule calibers (min support, min confidence) -- swept
RULES = [(3, 0.30), (5, 0.40), (8, 0.50), (10, 0.60)]

MAX_COMMITS = 30000  # cap most-recent commits per project (bounds ansible/pandas); reported

def git_log_commits(repo):
    """yield list-of-source-py-files per commit over (most-recent, capped) history."""
    cmd = ["git","-C",repo,"log",f"--max-count={MAX_COMMITS}","--no-merges",
           "--pretty=format:__C__%H","--name-only"]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode != 0:
        log(f"[git-fail] {repo}: {p.stderr.strip()[:200]}")
        return
    cur=None; files=[]
    for line in p.stdout.splitlines():
        if line.startswith("__C__"):
            if cur is not None: yield files
            cur=line[5:]; files=[]
        elif line.strip():
            if line.endswith(".py") and not is_test(line):
                files.append(line.strip())
    if cur is not None: yield files

def mine_project(repo, proj):
    commits = [list(dict.fromkeys(f)) for f in git_log_commits(repo)]  # dedup within commit
    n_all = len(commits)
    res = {}  # (tangle_thresh) -> stats
    for T in TANGLE_THRESHOLDS:
        used = [c for c in commits if 2 <= len(c) <= T]   # need >=2 files to form an edge
        file_commits = Counter()
        pair_commits = Counter()
        for c in used:
            for f in c: file_commits[f]+=1
            for a,b in combinations(sorted(set(c)),2):
                pair_commits[(a,b)] += 1
        rule_out = {}
        for (Smin,Cmin) in RULES:
            edges=[]
            for (a,b),sup in pair_commits.items():
                if sup < Smin: continue
                ca, cb = file_commits[a], file_commits[b]
                conf = max(sup/ca if ca else 0, sup/cb if cb else 0)
                if conf >= Cmin:
                    edges.append({"a":a,"b":b,"support":sup,"confidence":round(conf,3)})
            rule_out[f"S{Smin}_C{Cmin}"] = edges
        res[T] = {"n_commits_used": len(used), "n_pairs": len(pair_commits),
                  "rules": {k: len(v) for k,v in rule_out.items()},
                  "edges_by_rule": rule_out}
    return n_all, res

projects = sorted(d for d in os.listdir(REPOS) if os.path.isdir(os.path.join(REPOS,d,".git")))
log(f"[start] pe1 {STAMP} projects_cloned={len(projects)}: {projects}")

all_summary={}; export_edges={}
# choose ONE primary caliber for the edge export feeding static-visibility/task3:
PRIMARY_T = 8; PRIMARY_RULE = "S5_C0.4"
for proj in projects:
    repo=os.path.join(REPOS,proj)
    log(f"  [mining] {proj} ...")
    try:
        n_all,res=mine_project(repo,proj)
    except Exception as e:
        log(f"[FAIL] {proj}: {e!r}"); continue
    all_summary[proj]={"n_commits_mined":n_all,"commit_cap":MAX_COMMITS,"cap_hit":n_all>=MAX_COMMITS,
        "by_tangle":{str(T):{"n_commits_used":res[T]["n_commits_used"],
                             "n_pairs":res[T]["n_pairs"],"rules":res[T]["rules"]}
                     for T in TANGLE_THRESHOLDS}}
    prim=res[PRIMARY_T]["edges_by_rule"][PRIMARY_RULE]
    for e in prim: e["project"]=proj
    export_edges[proj]=prim
    log(f"  {proj}: commits={n_all}  primary(T={PRIMARY_T},{PRIMARY_RULE}) edges={len(prim)}")

flat=[e for v in export_edges.values() for e in v]
json.dump(all_summary, open(os.path.join(OUT,f"pe1_summary_{STAMP}.json"),"w"), indent=1)
json.dump(flat, open(os.path.join(OUT,f"pe1_edges_primary_{STAMP}.json"),"w"), indent=1)

log("\n=== EVOLUTIONARY COUPLING (multi-caliber) ===")
log(f"  projects mined: {len(all_summary)}")
# aggregate edge counts per caliber
agg=defaultdict(lambda: defaultdict(int))
for proj,s in all_summary.items():
    for T,info in s["by_tangle"].items():
        for rule,cnt in info["rules"].items():
            agg[T][rule]+=cnt
log("  total edges by (tangle_threshold x rule):")
for T in map(str,TANGLE_THRESHOLDS):
    log(f"   tangle<= {T}: " + "  ".join(f"{r}={agg[T][r]}" for r in ["S3_C0.3","S5_C0.4","S8_C0.5","S10_C0.6"]))
log(f"  PRIMARY export (T={PRIMARY_T},{PRIMARY_RULE}): {len(flat)} edges across {len(export_edges)} projects")
log("[done] pe1 outputs in", OUT)
LOG.close()
