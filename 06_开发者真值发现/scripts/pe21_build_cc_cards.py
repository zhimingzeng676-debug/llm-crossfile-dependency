"""
M59 Task1 (CPU): build co-change SUPPLEMENT cards for each seed.
Supplement card = high-confidence co-change partners of the seed (from evo git history),
which cover the static-invisible blind-spot edges. De-noised (drop setup/version/doc/test
noise partners, per M54), report raw vs denoised counts. Also build equal-length filler
(for the token-control condition, M56 lesson).

HONEST: the co-change partners are the SAME source as the gold co-change edges, so high
recall under static+cochange = "model reads the supplied co-change card" (feed-structure
mechanism, like the static card on visible edges) — a METHOD demonstration, NOT a discovery
of new model ability. Transparent by design. co-change != dependency.
"""
import json, os, re, glob
T3=r"D:\claude\59\pilot_devtruth\task3"; OUT=r"D:\claude\59\pilot_devtruth\out"
NOISE=re.compile(r"(changelog|history|news|release|version|__about__|__version__|/docs?/|/doc/|"
    r"/examples?/|/tutorials?/|/samples?/|conftest|/tests?/|test_|_test\.py|setup\.py|setup\.cfg|"
    r"/locale/|/data/|/fixtures?/|/benchmarks?/|/website/|migrations?)", re.I)
def is_noise(p): return bool(NOISE.search("/"+p))

# evo co-change adjacency (partners + confidence) per project
evo=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
adj={}  # (project, file) -> list of (partner, support, conf)
for e in evo:
    for a,b in [(e["a"],e["b"]),(e["b"],e["a"])]:
        adj.setdefault((e["project"],a),[]).append((b,e.get("support",0),e.get("confidence",0)))

FILLER=("This section contains general repository background notes and coding conventions "
        "and is not specific to any particular module. ")
def filler(n):
    s=""
    while len(s)<n: s+=FILLER
    return s[:max(n,1)]

insts=json.load(open(os.path.join(T3,"instances_mech.json")))
out=[]; raw_parts=0; den_parts=0
for i in insts:
    partners=adj.get((i["project"],i["seed"]),[])
    partners=sorted(set(partners), key=lambda x:(-x[2],-x[1]))  # high confidence first
    raw_list=[p for p,_,_ in partners]
    den_list=[p for p,_,_ in partners if not is_noise(p)]
    raw_parts+=len(raw_list); den_parts+=len(den_list)
    cc_raw = ("Co-change history (files that historically change together with this file, "
              "from git history — may include runtime/dynamic coupling static analysis misses):\n"
              + ", ".join(raw_list)) if raw_list else "(no co-change history)"
    cc_den = ("Co-change history (files that historically change together with this file, "
              "from git history — may include runtime/dynamic coupling static analysis misses):\n"
              + ", ".join(den_list)) if den_list else "(no co-change history)"
    o={**i, "cochange_card": cc_den, "cochange_card_raw": cc_raw,
       "filler_cc": filler(len(cc_den))}
    out.append(o)
json.dump(out, open(os.path.join(T3,"instances_cc.json"),"w"), indent=1)
print(f"built instances_cc.json: {len(out)} instances")
print(f"  raw co-change partners avg={raw_parts/len(out):.1f}; denoised avg={den_parts/len(out):.1f}")
print(f"  (denoise dropped {raw_parts-den_parts} noise partners = {(raw_parts-den_parts)/max(raw_parts,1)*100:.1f}%)")
# how many instances have >=1 invisible gold covered by the denoised co-change card?
cov=0; inv_tot=0; inv_cov=0
for o in out:
    ccset=set(re.split(r",\s*", o["cochange_card"].split("\n")[-1])) if "no co-change" not in o["cochange_card"] else set()
    has=False
    for g in o["gold"]:
        if g["layer"].startswith("invisible"):
            inv_tot+=1
            if g["file"] in ccset: inv_cov+=1; has=True
    if has: cov+=1
print(f"  invisible gold edges covered by denoised co-change card: {inv_cov}/{inv_tot} ({inv_cov/inv_tot*100:.1f}%)")
print(f"  (this is the method's coverage ceiling for blind-spot edges)")
