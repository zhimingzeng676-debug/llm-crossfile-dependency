# -*- coding: utf-8 -*-
"""跨模型 det gold-recall 打分(judge-independent)。读 <REMOTE_WORKDIR>/xmodel/ans_<model>_<cond>.json。"""
import json, os
B = "<REMOTE_WORKDIR>/phaseB"; X = "<REMOTE_WORKDIR>/xmodel"
gold = {}
for b in json.load(open(os.path.join(B, "bundle_werkzeug_baseline_general.json"), encoding="utf-8")):
    gold[b["id"]] = ([g.strip().lower() for g in b["gold"].split(",") if g.strip()], b.get("difficulty"))

def detrec(f):
    d = json.load(open(f, encoding="utf-8")); run = d["runs"][0]
    num = den = hn = hd = 0.0
    for r in run:
        kws, diff = gold[r["id"]]; t = (r["answer"] or "").lower()
        rec = sum(1 for k in kws if k in t) / len(kws) if kws else 0.0
        num += rec; den += 1
        if diff == "hard": hn += rec; hd += 1
    return num / den, (hn / hd if hd else None), int(den)

MODELS = ["qwen14b", "intern7b", "llama8b", "coder14b"]
CONDS = ["baseline", "full", "pecot"]
res = {}
for m in MODELS:
    row = {}
    for c in CONDS:
        f = os.path.join(X, f"ans_{m}_{c}.json")
        if os.path.exists(f):
            r, h, n = detrec(f); row[c] = dict(recall=round(r, 4), hard=round(h, 4) if h else None, n=n)
    if row: res[m] = row
json.dump(res, open(os.path.join(X, "xmodel_scores.json"), "w"), ensure_ascii=False, indent=1)

print("=== 跨模型主线三件(det gold-recall, judge-independent, werkzeug 56)===")
print(f"{'model':10}{'baseline':>10}{'full(RAG)':>11}{'pecot(PE+RAG)':>15}{'RAG杠杆×':>10}{'PE增量':>9}")
for m in MODELS:
    if m not in res: print(f"{m:10}(missing)"); continue
    r = res[m]
    bl = r.get("baseline", {}).get("recall"); fu = r.get("full", {}).get("recall"); pc = r.get("pecot", {}).get("recall")
    lev = f"{fu/bl:.1f}x" if (bl and fu and bl > 0) else "—"
    pe = f"{pc-fu:+.3f}" if (pc is not None and fu is not None) else "—"
    print(f"{m:10}{(bl if bl is not None else 0):>10.4f}{(fu if fu is not None else 0):>11.4f}{(pc if pc is not None else 0):>15.4f}{lev:>10}{pe:>9}")
print("\n判读:RAG杠杆×=full/baseline(各模型是否都大效应);PE增量=pecot−full(PE在RAG之上各模型是否都边际)。")
print("XMSCORE_DONE")
