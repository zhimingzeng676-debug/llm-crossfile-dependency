"""
M59 analysis (CPU): open-gen recall by layer under static_only / static+cochange /
static+filler. Tests: does co-change supplement card improve static-invisible recall
beyond static-only AND beyond equal-length filler (token control)? No visible degradation?
HONEST: cochange card is same-source as gold (covers ~98% invisible gold) -> high recall =
'model uses supplied co-change edges' (feed-structure), not new model ability.
"""
import json, os, re
T3=r"D:\claude\59\pilot_devtruth\task3"
def pred_sets(raw):
    paths=set(); m=re.search(r"\[.*\]",raw,re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x,str): paths.add(x.strip())
        except Exception: pass
    for t in re.findall(r"[\w./\\-]+\.py",raw): paths.add(t.strip().strip('"').strip("'"))
    paths={p.replace("\\","/").lstrip("./") for p in paths if p}
    return {os.path.basename(p) for p in paths}, paths
def load(cond):
    d=json.load(open(os.path.join(T3,f"scores_cc_{cond}.json")))
    r=d["results"] if isinstance(d,dict) else d
    return {(x["project"],x["seed"]):x for x in r if not x.get("err")}

conds=["open_staticcard","open_static_cochange","open_static_filler"]
data={c:load(c) for c in conds}
keys=set.intersection(*[set(data[c].keys()) for c in conds])
print(f"=== M59 co-change augmentation (open-gen, basename caliber); common instances={len(keys)} ===")
agg={c:{} for c in conds}; npred={c:[] for c in conds}
for k in keys:
    gold=data[conds[0]][k]["gold"]
    for c in conds:
        pb,full=pred_sets(data[c][k]["raw"]); npred[c].append(len(full))
        for g in gold:
            lay=g["layer"]; a=agg[c].setdefault(lay,[0,0]); a[1]+=1
            a[0]+= os.path.basename(g["file"]) in pb
            ia=agg[c].setdefault("invisible_all",[0,0])
            if lay.startswith("invisible"): ia[1]+=1; ia[0]+= os.path.basename(g["file"]) in pb
print(f"\n{'condition':24}{'visible':>14}{'invisible_all':>16}{'invis_dynamic':>16}{'invis_namematch':>17}{'mean_preds':>12}")
for c in conds:
    def r(l):
        v=agg[c].get(l); return f"{v[0]/v[1]:.3f}" if v and v[1] else "-"
    mp=sum(npred[c])/len(npred[c])
    print(f"{c:24}{r('visible'):>14}{r('invisible_all'):>16}{r('invisible_dynamic'):>16}{r('invisible_namematch'):>17}{mp:>12.1f}")
print("\nKEY comparisons (invisible_all):")
def rate(c,l):
    v=agg[c].get(l); return v[0]/v[1] if v and v[1] else 0
print(f"  static+cochange - static_only  = {rate('open_static_cochange','invisible_all')-rate('open_staticcard','invisible_all'):+.3f}  (improvement)")
print(f"  static+cochange - static+filler= {rate('open_static_cochange','invisible_all')-rate('open_static_filler','invisible_all'):+.3f}  (rules out token-count)")
print(f"  visible: cochange {rate('open_static_cochange','visible'):.3f} vs static_only {rate('open_staticcard','visible'):.3f}  (degradation check)")
print("\nHONEST: cochange card ~= gold (same-source, covers ~98% invisible gold); high recall = model USES supplied co-change edges (feed-structure), not new ability.")
