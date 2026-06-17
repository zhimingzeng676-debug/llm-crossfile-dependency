"""
M54 (CPU): re-slice the EXISTING bug-fix scores (M50) by noise/core.
Bug-fix co-change = files a developer changed to fix ONE real bug = the strongest
'real task coupling' signal available (much less process-noise than historical
co-commits). Does the negative lever hold on bug-fix invisible core_both edges?
No new GPU run; re-analysis of scores_bugfix_*.json. co-change != dependency.
"""
import json, os, re, math
T3=r"D:\claude\59\pilot_devtruth\task3"
NOISE_RE=re.compile(r"(changelog|history|news|release|version|__about__|__version__|"
    r"/docs?/|/doc/|/examples?/|/tutorials?/|/samples?/|conftest|/tests?/|test_|_test\.py|"
    r"setup\.py|setup\.cfg|/locale/|/data/|/fixtures?/|/benchmarks?/|/website/|migrations?)", re.I)
def is_noise(p): return bool(NOISE_RE.search("/"+p))

def reslice(rows,label):
    n=len(rows)
    if n==0: print(f"  {label:36} n=0"); return
    nc=sum(r["nc"] for r in rows)/n; st=sum(r["st"] for r in rows)/n
    b01=sum(1 for r in rows if r["st"] and not r["nc"]); b10=sum(1 for r in rows if r["nc"] and not r["st"])
    m=b01+b10; k=min(b01,b10); p=min(1.0,2*sum(math.comb(m,i) for i in range(k+1))/(2**m)) if m else None
    ps=f"p={p:.3g}" if p is not None else "p=NA"
    print(f"  {label:36} n={n:4} no_card={nc:.3f} static={st:.3f} Δ={nc-st:+.3f} (nc-only={b10} st-only={b01} {ps})")

for variant in ["bugfix_raw","bugfix_denoised"]:
    insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,f"instances_{variant}.json")))}
    sc=json.load(open(os.path.join(T3,f"scores_{variant}.json")))
    pred={(r["project"],r["seed"]):r["preds"] for r in sc["results"] if not r.get("_err")}
    recs=[]
    for key,inst in insts.items():
        if key not in pred: continue
        nc=set(pred[key].get("no_card",[])); st=set(pred[key].get("static_card",[]))
        for g in inst["gold"]:
            if not g["layer"].startswith("invisible"): continue
            cls="noise" if (is_noise(inst["seed"]) or is_noise(g["file"])) else "core_both"
            recs.append({"layer":g["layer"],"cls":cls,"nc":g["file"] in nc,"st":g["file"] in st})
    print(f"\n=== {variant} (bug-fix = real-task-coupling gold) ===")
    inv=[r for r in recs if r["layer"].startswith("invisible")]
    nz=sum(1 for r in inv if r["cls"]=="noise")
    print(f"  invisible edges total={len(inv)}  core_both={len(inv)-nz} ({(len(inv)-nz)/max(len(inv),1)*100:.0f}%)  noise={nz}")
    reslice(inv,"all invisible")
    reslice([r for r in inv if r["cls"]=="core_both"],"core_both (real-dep-likely)")
    reslice([r for r in recs if r["layer"]=="invisible_dynamic" and r["cls"]=="core_both"],"invisible_dynamic core_both")
    reslice([r for r in recs if r["layer"]=="invisible_namematch" and r["cls"]=="core_both"],"invisible_namematch core_both")
