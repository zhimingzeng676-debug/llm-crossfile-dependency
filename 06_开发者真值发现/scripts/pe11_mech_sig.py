"""M52: paired significance (McNemar) for mechanism result.
Per invisible gold edge, recall outcome under each condition; McNemar no_card vs
static_card (and vs filler/random). Judge-independent; no conclusion."""
import json, os, math
T3=r"D:\claude\59\pilot_devtruth\task3"
insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_mech.json")))}
sc=json.load(open(os.path.join(T3,"scores_mech.json")))
pred={(r["project"],r["seed"]):r["preds"] for r in sc["results"]}

def edges(layerpfx):
    rows=[]
    for inst in insts.values():
        key=(inst["project"],inst["seed"])
        if key not in pred: continue
        p=pred[key]
        for g in inst["gold"]:
            if not g["layer"].startswith(layerpfx): continue
            rows.append({l:(g["file"] in set(p.get(l,[]))) for l in
                         ["no_card","static_card","filler_card","random_card"]})
    return rows

def mcnemar(rows,a,b):
    # b01 = a wrong, b right ; b10 = a right, b wrong
    b01=sum(1 for r in rows if (not r[a]) and r[b])
    b10=sum(1 for r in rows if r[a] and (not r[b]))
    n=b01+b10
    if n==0: return b01,b10,None
    # binomial two-sided exact p (continuity-free), under p=0.5
    k=min(b01,b10)
    p=2*sum(math.comb(n,i) for i in range(0,k+1))/(2**n)
    return b01,b10,min(p,1.0)

for layer in ["invisible","invisible_dynamic","invisible_namematch","visible"]:
    rows=edges(layer)
    n=len(rows)
    print(f"\n=== {layer} (n={n} edges) ===")
    for cond in ["no_card","filler_card","random_card","static_card"]:
        r=sum(x[cond] for x in rows)
        print(f"  {cond:14} recall={r/n:.3f} ({r}/{n})")
    for a,b in [("static_card","no_card"),("static_card","filler_card"),("static_card","random_card")]:
        b01,b10,p=mcnemar(rows,a,b)
        # recall(b)-recall(a): b10 = a-only right, b01 = b-only right
        print(f"  McNemar {b} vs {a}: {b}-only={b01} {a}-only={b10} p={p:.4g}" if p is not None else f"  {b} vs {a}: no discordant")
