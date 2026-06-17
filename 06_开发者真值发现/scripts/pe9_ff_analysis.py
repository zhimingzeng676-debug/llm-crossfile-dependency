"""
M51 Task1b: false-friend precision test. In the falsefriends pool, decoys =
candidates filename-similar to the seed but NOT co-changed (not gold). If no_card
is filename-driven it should FALSELY pick these. Measure decoy false-pick rate
vs true-gold recall. co-change != dependency; no conclusion.
"""
import json, os, re
T3=r"D:\claude\59\pilot_devtruth\task3"
def toks(p):
    b=os.path.basename(p); b=b[:-3] if b.endswith(".py") else b
    return set(t for t in re.split(r"[_\W]+",b.lower()) if t)
def sim(a,b): return bool(toks(a)&toks(b))

insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_ctrl_falsefriends.json")))}
sc=json.load(open(os.path.join(T3,"scores_ctrl_falsefriends.json")))
if "summary" in sc:
    print("=== falsefriends recall (summary) ===")
    for cond in ["no_card","static_card"]:
        s=sc["summary"].get(cond,{})
        print(f"  {cond:12}",{l:f"{s[l]['recall']}({s[l]['recalled']}/{s[l]['total']})" for l in sorted(s)})

# precision on decoys
err=0
decoy_off=decoy_pick_nc=decoy_pick_sc=0
goldfn_dissim_off=goldfn_dissim_rec_nc=0
clean_n=0
for r in sc["results"]:
    key=(r["project"],r["seed"]); inst=insts.get(key)
    if not inst: continue
    if r.get("_err"): err+=1; continue   # EXCLUDE errored instances (partial-run safe)
    clean_n+=1
    nc=set(r["preds"].get("no_card",[])); scd=set(r["preds"].get("static_card",[]))
    goldset={g["file"] for g in inst["gold"]}
    seed=inst["seed"]
    for c in inst["candidates"]:
        if c in goldset: continue
        if sim(c,seed):   # decoy: filename-similar to seed, not gold
            decoy_off+=1
            if c in nc: decoy_pick_nc+=1
            if c in scd: decoy_pick_sc+=1
    # recall on filename-dissimilar gold (true capture)
    for g in inst["gold"]:
        if not sim(g["file"],seed):
            goldfn_dissim_off+=1
            if g["file"] in nc: goldfn_dissim_rec_nc+=1

print(f"\nclean_instances_used={clean_n}  err_instances_excluded={err}")
print(f"\n=== DECOY false-pick (filename-similar-to-seed, NOT cochange) ===")
print(f"  decoys offered={decoy_off}")
print(f"  no_card false-picked={decoy_pick_nc} rate={decoy_pick_nc/decoy_off:.3f}" if decoy_off else "  none")
print(f"  static_card false-picked={decoy_pick_sc} rate={decoy_pick_sc/decoy_off:.3f}" if decoy_off else "")
print(f"\n=== no_card recall on FILENAME-DISSIMILAR gold (true capture) ===")
print(f"  dissimilar gold offered={goldfn_dissim_off}  no_card recalled={goldfn_dissim_rec_nc} rate={goldfn_dissim_rec_nc/goldfn_dissim_off:.3f}" if goldfn_dissim_off else "  none")
print("\nINTERPRETATION KEYS (for human): if decoy false-pick rate << gold recall => NOT filename-driven (model distinguishes real co-change from filename lookalikes).")
