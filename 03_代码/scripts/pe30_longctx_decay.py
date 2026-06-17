"""M66 analysis (CPU): dependency-recall decay vs context length + position
(lost-in-the-middle). keyword_all recall per condition. judge-independent."""
import json, os
T3=r"D:/claude/59/pilot_devtruth/task3"
d=json.load(open(os.path.join(T3,"scores_longctx.json")))
res=d["results"] if isinstance(d,dict) else d
CONDS=["short","mid","long_start","long_mid","long_end"]
def kwrec(text,kws): t=(text or "").lower(); return sum(1 for k in kws if k in t)/len(kws) if kws else 0
agg={c:[] for c in CONDS}
for r in res:
    for c in CONDS:
        agg[c].append(kwrec(r["ans"].get(c,""), r["keywords"]))
print(f"=== M66 长上下文丢失诊断:依赖召回(keyword_all det-recall, n={len(res)} werkzeug)===")
print(f"\n{'condition':12}{'ctx长度':>10}{'dep_recall':>12}")
labels={"short":"~card","mid":"~16k字","long_start":"~44k字 卡片在开头","long_mid":"~44k字 卡片在中间","long_end":"~44k字 卡片在末尾"}
def avg(xs): return sum(xs)/len(xs) if xs else 0
for c in CONDS:
    print(f"  {c:18}{avg(agg[c]):.3f}   ({labels[c]})")
print(f"\n衰减(vs short): mid Δ={avg(agg['mid'])-avg(agg['short']):+.3f}; long(best pos) Δ={max(avg(agg['long_start']),avg(agg['long_mid']),avg(agg['long_end']))-avg(agg['short']):+.3f}")
print(f"位置效应(long): start={avg(agg['long_start']):.3f} mid={avg(agg['long_mid']):.3f} end={avg(agg['long_end']):.3f}")
print(f"  lost-in-the-middle: 中间 vs (开头,末尾)均值 Δ={avg(agg['long_mid'])-(avg(agg['long_start'])+avg(agg['long_end']))/2:+.3f}")
json.dump({c:avg(agg[c]) for c in CONDS},open(r"D:/claude/59/pilot_devtruth/out/pe30_longctx.json","w"))
