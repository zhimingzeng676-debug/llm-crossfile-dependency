"""
Phase 2 (CPU, judge-independent): classify each developer co-change edge as
static_visible vs static_invisible, at IMPORT granularity, multi-caliber.

Method (deterministic): for a co-change pair (A,B) in the same repo at the bug's
fixed_commit, fetch A and B raw contents, parse imports with `ast`, resolve module
names, and check if A imports B's module (or vice versa).

HONEST LIMITATIONS (must be read with every number):
- IMPORT-level + direct-edge only. Does NOT run the project's tree-sitter repo_parser
  (which also builds inheritance/call edges over the whole repo). So this is a
  CONSERVATIVE proxy: it may UNDER-count static-visible (miss call/inheritance edges),
  i.e. it may OVER-state the static-invisible "blind spot". The authoritative
  classification should later re-run repo_parser on a full checkout (server phase).
- Module<-file mapping is derived from the repo-root-relative path in the patch.
- We only see the two changed files, not transitive imports.
- co-change != dependency: an edge is a 'co-change edge', never called a dependency.
Multi-caliber reported (strict/med/loose); nothing hidden.
"""
import os, re, json, glob, ast, urllib.request, time, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
BLOBS = os.path.join(OUT, "blobs")
os.makedirs(BLOBS, exist_ok=True)
STAMP = sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d_%H%M%S")
LOG = open(os.path.join(OUT, f"p2_log_{STAMP}.txt"), "w", encoding="utf-8")
def log(*a):
    s=" ".join(str(x) for x in a); print(s); LOG.write(s+"\n"); LOG.flush()

recs = json.load(open(sorted(glob.glob(os.path.join(OUT,"p1_records_*.json")))[-1], encoding="utf-8"))
edges = json.load(open(sorted(glob.glob(os.path.join(OUT,"p1_edges_untangled_*.json")))[-1], encoding="utf-8"))
slug = {}
for r in recs:
    if r["project"] not in slug and r["github"]:
        m = re.search(r"github\.com/([^/]+/[^/.]+)", r["github"])
        if m: slug[r["project"]] = m.group(1)

def fetch(project, commit, path):
    safe = path.replace("/", "__")
    cache = os.path.join(BLOBS, project, commit[:10])
    os.makedirs(cache, exist_ok=True)
    fp = os.path.join(cache, safe)
    if os.path.exists(fp):
        return open(fp, encoding="utf-8", errors="replace").read()
    url = f"https://raw.githubusercontent.com/{slug[project]}/{commit}/{path}"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"pilot-devtruth"})
            data = urllib.request.urlopen(req, timeout=30).read().decode("utf-8","replace")
            open(fp, "w", encoding="utf-8").write(data)
            return data
        except Exception as e:
            if attempt == 2:
                log(f"[fetch-fail] {project} {commit[:8]} {path} :: {e!r}")
                return None
            time.sleep(1.5)

def path_to_module(path):
    p = path[:-3] if path.endswith(".py") else path
    parts = p.split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts), parts  # module, parts

def package_parts_of(path):
    """package dir parts of a file (for resolving relative imports)."""
    p = path[:-3] if path.endswith(".py") else path
    parts = p.split("/")
    if parts and parts[-1] == "__init__":
        return parts[:-1]
    return parts[:-1]

def imports_of(src, file_path):
    """Return set of absolute module strings that this file imports.
    Relative imports resolved against file's package parts."""
    mods = set()
    if src is None:
        return mods, False
    try:
        tree = ast.parse(src)
    except Exception:
        return mods, True  # parse error flagged
    pkg = package_parts_of(file_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            base = node.module or ""
            if level == 0:
                if base:
                    mods.add(base)
                    for n in node.names:
                        mods.add(base + "." + n.name)
            else:
                # relative: go up (level-1) from package
                up = pkg[:len(pkg) - (level - 1)] if (level - 1) <= len(pkg) else []
                root = ".".join(up)
                if base:
                    full = (root + "." + base) if root else base
                else:
                    full = root
                if full:
                    mods.add(full)
                    for n in node.names:
                        mods.add(full + "." + n.name)
    return mods, False

def basename_stem(path):
    b = os.path.basename(path)
    return b[:-3] if b.endswith(".py") else b

def classify_edge(e):
    A, B = e["a"], e["b"]
    proj, commit = e["project"], e["fixed_commit"]
    srcA = fetch(proj, commit, A)
    srcB = fetch(proj, commit, B)
    fetched = (srcA is not None) and (srcB is not None)
    modA, _ = path_to_module(A)
    modB, _ = path_to_module(B)
    impA, errA = imports_of(srcA, A)
    impB, errB = imports_of(srcB, B)

    def hits(imps, target_mod, target_parts_path):
        """strict: exact module of target in imports.
        med: also prefix (import an ancestor package of target, or target ancestor)."""
        strict = target_mod in imps
        med = strict
        for m in imps:
            if m == target_mod: med = True
            # importing target's package (ancestor) -> via __init__ may expose target
            if target_mod.startswith(m + ".") or m.startswith(target_mod + "."):
                med = True
        return strict, med

    sA2B, mA2B = hits(impA, modB, B)
    sB2A, mB2A = hits(impB, modA, A)
    strict = sA2B or sB2A
    med = mA2B or mB2A
    # loose: textual reference of the other file's module stem as identifier
    stemA, stemB = basename_stem(A), basename_stem(B)
    loose = med
    if not loose and srcA and re.search(r"\b"+re.escape(stemB)+r"\b", srcA): loose = True
    if not loose and srcB and re.search(r"\b"+re.escape(stemA)+r"\b", srcB): loose = True

    # sub-type for static_invisible (under MED caliber)
    subtype = None
    if not med:
        textAB = (srcA or "") + "\n" + (srcB or "")
        dyn = re.search(r"__import__|importlib|getattr\(|globals\(\)|register|plugin|entry_point|exec\(|eval\(", textAB)
        same_dir = os.path.dirname(A) == os.path.dirname(B)
        is_init = A.endswith("__init__.py") or B.endswith("__init__.py")
        if not fetched:
            subtype = "fetch_failed"
        elif dyn:
            subtype = "dynamic_or_registry_hint"
        elif is_init:
            subtype = "package_init_coupling"
        elif same_dir:
            subtype = "same_dir_sibling_no_static_edge"
        else:
            subtype = "cross_dir_no_static_edge"
    return {**e, "modA": modA, "modB": modB, "fetched": fetched,
            "parse_err": bool(errA or errB),
            "strict": strict, "med": med, "loose": loose,
            "invisible_subtype": subtype}

log(f"[start] p2 {STAMP}  edges={len(edges)}")
results = []
for i, e in enumerate(edges):
    r = classify_edge(e)
    results.append(r)
    if (i+1) % 20 == 0:
        log(f"  {i+1}/{len(edges)} processed")

with open(os.path.join(OUT, f"p2_edge_class_{STAMP}.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, indent=1)

# ---- aggregate, multi-caliber ----
fetched = [r for r in results if r["fetched"]]
n = len(fetched)
def rate(key): return round(sum(1 for r in fetched if r[key])/n, 4) if n else None
summary = {
    "stamp": STAMP,
    "n_edges_total": len(results),
    "n_edges_fetched_ok": n,
    "n_fetch_failed": len(results) - n,
    "static_visible_rate": {
        "strict_import_exact": rate("strict"),
        "med_import_or_package_or_relative": rate("med"),
        "loose_incl_textual_stem": rate("loose"),
    },
    "static_invisible_rate": {
        "under_strict": round(1 - rate("strict"), 4) if n else None,
        "under_med": round(1 - rate("med"), 4) if n else None,
        "under_loose": round(1 - rate("loose"), 4) if n else None,
    },
    "invisible_subtype_counts_under_med": {},
    "per_project_med": {},
}
sub = {}
for r in fetched:
    if not r["med"]:
        sub[r["invisible_subtype"]] = sub.get(r["invisible_subtype"],0)+1
summary["invisible_subtype_counts_under_med"] = dict(sorted(sub.items(), key=lambda x:-x[1]))
pp = {}
for r in fetched:
    p = r["project"]; pp.setdefault(p, {"edges":0,"visible_med":0})
    pp[p]["edges"]+=1; pp[p]["visible_med"]+= 1 if r["med"] else 0
summary["per_project_med"] = pp

with open(os.path.join(OUT, f"p2_summary_{STAMP}.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=1)

log("\n=== STATIC VISIBILITY (import-level, multi-caliber) ===")
log(f"  edges fetched ok: {n}/{len(results)}  (fetch_failed={len(results)-n})")
log(f"  static_VISIBLE  strict={summary['static_visible_rate']['strict_import_exact']}"
    f"  med={summary['static_visible_rate']['med_import_or_package_or_relative']}"
    f"  loose={summary['static_visible_rate']['loose_incl_textual_stem']}")
log(f"  static_INVISIBLE strict={summary['static_invisible_rate']['under_strict']}"
    f"  med={summary['static_invisible_rate']['under_med']}"
    f"  loose={summary['static_invisible_rate']['under_loose']}")
log("  invisible subtypes (under med):", summary["invisible_subtype_counts_under_med"])
log("[done] p2 outputs in", OUT)
LOG.close()
