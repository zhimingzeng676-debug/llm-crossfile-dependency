"""M56: per-condition mean #predictions + total recall (all layers) for in-pool run,
to reconcile with round-10 judge's 'not fixed-budget reallocation' attack."""
import json, os
T3=r"D:\claude\59\pilot_devtruth\task3"
insts={(i["project"],i["seed"]):i for i in json.load(open(os.path.join(T3,"instances_mech_inpool.json")))}
d=json.load(open(os.path.join(T3,"scores_mech_inpool.json")))
pred={(r["project"],r["seed"]):r["preds"] for r in d["results"] if not r.get("_err")}
conds=["no_card","static_card","random_in_pool"]
npred={c:[] for c in conds}; correct={c:0 for c in conds}; total=0
for key,inst in insts.items():
    if key not in pred: continue
    gold={g["file"] for g in inst["gold"]}
    total_inst=len(gold)
    for c in conds:
        ps=set(pred[key].get(c,[])); npred[c].append(len(ps))
        correct[c]+= len(ps & gold)
    total+=total_inst
print(f"{'cond':16}{'mean_preds':>12}{'total_correct':>14}{'total_recall(all layers)':>26}")
for c in conds:
    mp=sum(npred[c])/len(npred[c]); print(f"{c:16}{mp:12.2f}{correct[c]:14}{correct[c]/total:26.3f}")
print(f"\ntotal gold (all layers, invisible-subset instances) = {total}")
print("\nReconcile w/ round-10 judge attack ('static outputs more yet recalls less => not budget'):")
print(" if random_in_pool ALSO outputs more & recalls less like static => the effect is")
print(" 'any in-pool card list crowds/worsens', NOT content-specific (judge's content claim refuted).")
