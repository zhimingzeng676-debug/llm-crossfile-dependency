"""
M61 analysis (CPU): end-to-end decay curve. For each (coverage,precision) config,
invisible recall vs TRUE gold (basename) + model echo-rate of FALSE carded edges
(co-change noise harm; ties to downstream-harm: confident wrong). Anchors: static_only 0.18.
"""
import json, os, re
T3=r"D:\claude\59\pilot_devtruth\task3"
insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_decay.json")))}
CONFIGS=["cov100_p100","cov70_p100","cov50_p100","cov30_p100","cov10_p100","cov50_p50","cov30_p50","cov50_p30"]
def pb(raw):
    s=set(); m=re.search(r"\[.*\]",raw,re.S)
    if m:
        try:
            for x in json.loads(m.group(0)):
                if isinstance(x,str): s.add(os.path.basename(x.strip()))
        except Exception: pass
    for t in re.findall(r"[\w./\\-]+\.py",raw): s.add(os.path.basename(t))
    return s
def card_listed(txt):
    if "no co-change" in txt: return []
    return [x.strip() for x in re.split(r",\s*", txt.split("\n")[-1]) if x.strip()]

print(f"{'config':14}{'cov':>5}{'prec':>6}{'invis_recall':>14}{'false_echo_rate':>16}")
print(f"{'static_only':14}{'-':>5}{'-':>6}{'0.178':>14}{'-':>16}  (anchor)")
rows={}
for tag in CONFIGS:
    p=os.path.join(T3,f"scores_decay_{tag}.json")
    if not os.path.exists(p): print(f"{tag:14} (missing)"); continue
    d=json.load(open(p)); res=d["results"] if isinstance(d,dict) else d
    pred={(x["project"],x["seed"]):x for x in res if not x.get("err")}
    inv=[0,0]; fe=[0,0]
    cov=tag.split("_")[0].replace("cov",""); prec=tag.split("_")[1].replace("p","")
    for k,inst in insts.items():
        if k not in pred: continue
        out=pb(pred[k]["raw"]); goldbn={os.path.basename(g["file"]) for g in inst["gold"]}
        for g in inst["gold"]:
            if g["layer"].startswith("invisible"): inv[1]+=1; inv[0]+= os.path.basename(g["file"]) in out
        # false carded edges = listed - gold ; how many does model echo?
        listed=card_listed(inst["deg_cards"][tag])
        for f in listed:
            if os.path.basename(f) not in goldbn:
                fe[1]+=1; fe[0]+= os.path.basename(f) in out
    rows[tag]=(inv[0]/inv[1] if inv[1] else 0, fe[0]/fe[1] if fe[1] else 0)
    print(f"{tag:14}{cov+'%':>5}{prec+'%':>6}{rows[tag][0]:>14.3f}{(f'{rows[tag][1]:.3f}' if fe[1] else '-'):>16}")
print("\nKEY:")
print(f"  upper bound (cov100_p100, =M59 demo) invis_recall = {rows.get('cov100_p100',(0,))[0]:.3f}")
print(f"  static_only anchor = 0.178")
print("  invis_recall tracks coverage (model echoes carded TRUE edges); false_echo_rate = co-change-noise harm (model confidently outputs false edges).")
print("  realistic deployment ~ a mid coverage+noise config (e.g. cov50_p50 / cov30_p50): see above.")
