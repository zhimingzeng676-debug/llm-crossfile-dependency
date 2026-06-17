"""
M58 analysis (CPU): blind-spot warning confusion matrix vs keyword baseline,
beyond-keyword subset, keyword-FP rejection, and memory (rename) test.
"""
import json, os, sys
T3=r"D:\claude\59\pilot_devtruth\task3"
def cm(rows, predf, labf):
    tp=fp=tn=fn=0; n=0
    for r in rows:
        p=predf(r); l=labf(r)
        if p is None: continue
        n+=1
        if l==1 and p==1: tp+=1
        elif l==0 and p==1: fp+=1
        elif l==0 and p==0: tn+=1
        elif l==1 and p==0: fn+=1
    prec=tp/(tp+fp) if tp+fp else 0
    rec=tp/(tp+fn) if tp+fn else 0
    fpr=fp/(fp+tn) if fp+tn else 0
    f1=2*prec*rec/(prec+rec) if prec+rec else 0
    return dict(n=n,tp=tp,fp=fp,tn=tn,fn=fn,precision=round(prec,3),recall=round(rec,3),
                fp_rate=round(fpr,3),f1=round(f1,3))

def load(f):
    d=json.load(open(os.path.join(T3,f)))
    return d["results"] if isinstance(d,dict) else d

orig=load("scores_warn_orig.json")
res={r["id"]:r for r in orig}
print(f"=== M58 blind-spot warning (n={len(orig)}) ===")
ok=[r for r in orig if not r["err"] and r["pred"] is not None]
print(f"  parsed ok: {len(ok)}/{len(orig)}")

print("\n[MODEL confusion matrix]"); print("  ", cm(ok, lambda r:r["pred"], lambda r:r["label"]))
print("[KEYWORD baseline (narrow_kw -> predict YES)]")
print("  ", cm(ok, lambda r:1 if r["narrow_kw"] else 0, lambda r:r["label"]))

print("\n[Beyond-keyword test] positives WITHOUT narrow keyword (keyword baseline MISSES these):")
bk=[r for r in ok if r["label"]==1 and not r["narrow_kw"]]
mrec=sum(1 for r in bk if r["pred"]==1)/len(bk) if bk else None
print(f"  n={len(bk)}  model recall on beyond-keyword positives = {mrec}")
print(f"  (keyword baseline recall here = 0 by construction)")

print("\n[Keyword-FP rejection] negatives WITH narrow keyword (keyword baseline FALSE-positives):")
kfp=[r for r in ok if r["label"]==0 and r["narrow_kw"]]
mrej=sum(1 for r in kfp if r["pred"]==0)/len(kfp) if kfp else None
print(f"  n={len(kfp)}  model correctly says NO = {mrej}  (keyword baseline wrong on all)")

# memory test
rn_path=os.path.join(T3,"scores_warn_renamed.json")
if os.path.exists(rn_path):
    rn=load("scores_warn_renamed.json")
    rok=[r for r in rn if not r["err"] and r["pred"] is not None]
    print("\n[MEMORY test: renamed identifiers]")
    print("  model CM on renamed:", cm(rok, lambda r:r["pred"], lambda r:r["label"]))
    print("  => compare F1/recall to original; if holds => recognizes dynamic structure, not memory")
else:
    print("\n[memory test] scores_warn_renamed.json not present yet")
