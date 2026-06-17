"""
M54 (CPU): attack the round-10 vulnerable point — co-change != dependency.
Of the static-invisible co-change edges that static_card SUPPRESSES recall on,
how many are 'real-dependency-likely (core-source coupling)' vs 'process/noise'
(CHANGELOG/version/docs/examples/tests/packaging)? Does the negative lever SURVIVE
on the de-noised real-dependency subset?

Deterministic, non-parser, non-subjective heuristics. Honest: this is a PROXY for
"real dependency" (file-role + co-change strength), not subjective developer truth.
co-change != dependency. No conclusion; report both possible outcomes' evidence.
"""
import json, os, re, glob, math
T3=r"D:\claude\59\pilot_devtruth\task3"; OUT=r"D:\claude\59\pilot_devtruth\out"

# evo co-change strength lookup (support/confidence) from pe1
evo=json.load(open(sorted(glob.glob(os.path.join(OUT,"pe1_edges_primary_*.json")))[-1]))
strength={}
for e in evo:
    strength[(e["project"],frozenset((e["a"],e["b"])))]=(e.get("support",0),e.get("confidence",0))

NOISE_RE=re.compile(r"(changelog|history|news|release|version|__about__|__version__|"
    r"/docs?/|/doc/|/examples?/|/tutorials?/|/samples?/|conftest|/tests?/|test_|_test\.py|"
    r"setup\.py|setup\.cfg|/locale/|/data/|/fixtures?/|/benchmarks?/|/website/|migrations?)", re.I)
def is_noise_file(p): return bool(NOISE_RE.search("/"+p))
def edge_class(seed, gold):
    if is_noise_file(seed) or is_noise_file(gold): return "noise"
    return "core_both"

insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_mech.json")))}
sc=json.load(open(os.path.join(T3,"scores_mech.json")))
pred={(r["project"],r["seed"]):r["preds"] for r in sc["results"] if not r.get("_err")}

# Build per-edge records (invisible layers only)
recs=[]
for key,inst in insts.items():
    if key not in pred: continue
    nc=set(pred[key].get("no_card",[])); st=set(pred[key].get("static_card",[]))
    for g in inst["gold"]:
        if not g["layer"].startswith("invisible"): continue
        sup,conf=strength.get((inst["project"],frozenset((inst["seed"],g["file"]))),(0,0))
        recs.append({"proj":inst["project"],"seed":inst["seed"],"gold":g["file"],
                     "layer":g["layer"],"cls":edge_class(inst["seed"],g["file"]),
                     "sup":sup,"conf":conf,"nc":g["file"] in nc,"st":g["file"] in st})

def reslice(rows,label):
    n=len(rows)
    if n==0: print(f"  {label}: n=0"); return
    nc=sum(r["nc"] for r in rows)/n; st=sum(r["st"] for r in rows)/n
    # McNemar nc vs st
    b01=sum(1 for r in rows if r["st"] and not r["nc"])  # st-only
    b10=sum(1 for r in rows if r["nc"] and not r["st"])  # nc-only
    m=b01+b10; k=min(b01,b10)
    p=min(1.0,2*sum(math.comb(m,i) for i in range(k+1))/(2**m)) if m else None
    print(f"  {label:42} n={n:4}  no_card={nc:.3f} static={st:.3f}  Δ={nc-st:+.3f}  "
          f"(nc-only={b10} st-only={b01} p={p:.3g})" if p is not None else
          f"  {label:42} n={n:4}  no_card={nc:.3f} static={st:.3f}  Δ={nc-st:+.3f}")

print("=== Q1: of static-invisible co-change edges, noise vs core_both fraction ===")
for layer in ["invisible","invisible_dynamic","invisible_namematch"]:
    sub=[r for r in recs if r["layer"].startswith(layer)] if layer=="invisible" else [r for r in recs if r["layer"]==layer]
    nz=sum(1 for r in sub if r["cls"]=="noise"); cb=len(sub)-nz
    print(f"  {layer:22} total={len(sub)}  core_both={cb} ({cb/len(sub)*100:.0f}%)  noise={nz} ({nz/len(sub)*100:.0f}%)")

print("\n=== Q1b: among edges static_card SUPPRESSES (no_card recalled, static missed): noise vs core ===")
supp=[r for r in recs if r["nc"] and not r["st"]]
nz=sum(1 for r in supp if r["cls"]=="noise")
print(f"  suppressed invisible edges={len(supp)}  core_both={len(supp)-nz} ({(len(supp)-nz)/len(supp)*100:.0f}%)  noise={nz} ({nz/len(supp)*100:.0f}%)")

print("\n=== Q2: does negative lever (no_card>static) SURVIVE on de-noised / high-conf subsets? ===")
print(" [invisible_dynamic]")
dyn=[r for r in recs if r["layer"]=="invisible_dynamic"]
reslice(dyn,"all dynamic")
reslice([r for r in dyn if r["cls"]=="core_both"],"core_both (real-dep-likely)")
reslice([r for r in dyn if r["cls"]=="noise"],"noise (changelog/ver/docs/test)")
reslice([r for r in dyn if r["cls"]=="core_both" and r["conf"]>=0.6],"core_both & conf>=0.6")
print(" [invisible_namematch]")
nm=[r for r in recs if r["layer"]=="invisible_namematch"]
reslice(nm,"all namematch")
reslice([r for r in nm if r["cls"]=="core_both"],"core_both (real-dep-likely)")
reslice([r for r in nm if r["cls"]=="noise"],"noise")
reslice([r for r in nm if r["cls"]=="core_both" and r["conf"]>=0.6],"core_both & conf>=0.6")
print(" [invisible ALL]")
allinv=recs
reslice([r for r in allinv if r["cls"]=="core_both"],"core_both (real-dep-likely)")
reslice([r for r in allinv if r["cls"]=="noise"],"noise")
json.dump(recs,open(os.path.join(T3,"pe12_edge_recs.json"),"w"))
print("\n[pe12] dumped pe12_edge_recs.json")
