"""
M57 Task1 analysis (CPU): open-generation recall by static-visibility layer.
Match model's FREE path list against co-change gold. Multi-caliber path matching:
exact (gold path substring) / suffix>=2 components / basename. co-change != dependency.
Gate question: does invisible recall survive open generation (vs selection-task ~0.33)?
"""
import json, os, re, sys
T3=r"D:\claude\59\pilot_devtruth\task3"
F=sys.argv[1] if len(sys.argv)>1 else "scores_opengen_nocard.json"
d=json.load(open(os.path.join(T3,F)))
results=d["results"] if isinstance(d,dict) else d

def pred_paths(raw):
    """extract candidate file paths from free-form output."""
    paths=set()
    m=re.search(r"\[.*\]", raw, re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x,str): paths.add(x.strip())
        except Exception: pass
    # fallback: any *.py token (quoted or bare)
    for t in re.findall(r"[\w./\\-]+\.py", raw):
        paths.add(t.strip().strip('"').strip("'"))
    return {p.replace("\\","/").lstrip("./") for p in paths if p}

def suffix2(p):
    parts=p.split("/"); return "/".join(parts[-2:])
def base(p): return os.path.basename(p)

agg={}  # caliber -> layer -> [recalled,total]
nerr=0; pred_counts=[]
for r in results:
    if r.get("err"): nerr+=1; continue
    pp=pred_paths(r["raw"]); pred_counts.append(len(pp))
    pp_suffix={suffix2(p) for p in pp}; pp_base={base(p) for p in pp}
    for g in r["gold"]:
        y=g["file"].replace("\\","/").lstrip("./"); lay=g["layer"]
        hit_exact = y in pp or any(y in p or p in y for p in pp)
        hit_suffix = suffix2(y) in pp_suffix
        hit_base = base(y) in pp_base
        for cal,hit in [("exact",hit_exact),("suffix2",hit_suffix),("basename",hit_base)]:
            a=agg.setdefault(cal,{}).setdefault(lay,[0,0]); a[1]+=1; a[0]+=1 if hit else 0
            a2=agg.setdefault(cal,{}).setdefault("invisible_all",[0,0])
            if lay.startswith("invisible"): a2[1]+=1; a2[0]+=1 if hit else 0

print(f"=== open-gen recall ({F}); n_ok={len(results)-nerr} err={nerr}; mean_pred_paths={sum(pred_counts)/max(len(pred_counts),1):.1f} ===")
for cal in ["exact","suffix2","basename"]:
    print(f"\n  [{cal} match]")
    for lay in ["visible","invisible_all","invisible_dynamic","invisible_namematch"]:
        v=agg.get(cal,{}).get(lay)
        if v: print(f"    {lay:22} recall={v[0]/v[1]:.3f} ({v[0]}/{v[1]})")
print("\nGATE: compare invisible recall here vs selection-task no_card ~0.33 (M52).")
print(" if invisible recall collapses (~0) under open-gen => the 0.33 was selection-task artifact.")
print(" if invisible recall survives substantially => real open recall ability => Task2 (signal).")
