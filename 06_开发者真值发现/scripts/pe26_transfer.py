"""
M63 analysis (CPU): random vs systematic degradation transfer functions.
For each condition (rnd/sys at cov 0/25/50/75/100): effective invisible coverage
(fraction of invisible gold in card) and invisible recall (basename). Fit recall = a+b*cov
per regime via least squares. Report intercept (model floor), slope, and whether
systematic is steeper / lower at matched effective coverage. co-change != dependency.
"""
import json, os, re
T3=r"D:\claude\59\pilot_devtruth\task3"
insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_sysdecay.json")))}
def pb(raw):
    s=set(); m=re.search(r"\[.*\]",raw,re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x,str): s.add(os.path.basename(x.strip()))
        except Exception: pass
    for t in re.findall(r"[\w./\\-]+\.py",raw): s.add(os.path.basename(t))
    return s
def listed(txt): return [] if "no co-change" in txt else [x.strip() for x in re.split(r",\s*",txt.split("\n")[-1]) if x.strip()]

KEYS=["rnd_0","rnd_25","sys_25","rnd_50","sys_50","rnd_75","sys_75","rnd_100","sys_100"]
pts={}  # key -> (eff_cov, recall)
for key in KEYS:
    p=os.path.join(T3,f"scores_sweep_{key}.json")
    if not os.path.exists(p): print(f"{key} missing"); continue
    d=json.load(open(p)); res=d["results"] if isinstance(d,dict) else d
    pred={(x["project"],x["seed"]):x for x in res if not x.get("err")}
    rec=[0,0]; cov=[0,0]
    for k,inst in insts.items():
        if k not in pred: continue
        out=pb(pred[k]["raw"]); cardbn={os.path.basename(f) for f in listed(inst["sweep_cards"][key])}
        for g in inst["gold"]:
            if not g["layer"].startswith("invisible"): continue
            rec[1]+=1; rec[0]+= os.path.basename(g["file"]) in out
            cov[1]+=1; cov[0]+= os.path.basename(g["file"]) in cardbn
    pts[key]=(cov[0]/cov[1] if cov[1] else 0, rec[0]/rec[1] if rec[1] else 0)

def fit(keys):
    xs=[pts[k][0] for k in keys if k in pts]; ys=[pts[k][1] for k in keys if k in pts]
    n=len(xs); sx=sum(xs); sy=sum(ys); sxx=sum(x*x for x in xs); sxy=sum(x*y for x,y in zip(xs,ys))
    b=(n*sxy-sx*sy)/(n*sxx-sx*sx); a=(sy-b*sx)/n
    return a,b
print(f"{'condition':10}{'eff_cov':>10}{'invis_recall':>14}")
for key in KEYS:
    if key in pts: print(f"{key:10}{pts[key][0]:>10.3f}{pts[key][1]:>14.3f}")
rnd_keys=["rnd_0","rnd_25","rnd_50","rnd_75","rnd_100"]
sys_keys=["rnd_0","sys_25","sys_50","sys_75","sys_100"]  # cov0 shared
ar,br=fit(rnd_keys); asy,bsy=fit(sys_keys)
print(f"\nRANDOM     transfer: recall = {ar:.3f} + {br:.3f}*eff_cov")
print(f"SYSTEMATIC transfer: recall = {asy:.3f} + {bsy:.3f}*eff_cov")
print(f"static_only floor (cov=0): {pts.get('rnd_0',(0,0))[1]:.3f}")
print(f"\ncompare: old conservative '×0.97'(origin) vs judge '0.14+0.84cov' vs measured above.")
print("if systematic slope>random slope (steeper) and/or lower recall at matched eff_cov -> systematic harder, as judge predicted.")
print("NOTE: gold requires support>=5, so truly-never-co-changed edges excluded -> both bounds understate hardest real edges.")
