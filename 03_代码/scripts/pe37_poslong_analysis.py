"""M71 analysis (CPU): long-context POSITION effect (finer scan) + cross-model.
dep-recall per position {0,25,50,75,100} for coder & qwen. recency vs LITM. judge-independent."""
import json, os
T3=r"D:/claude/59/pilot_devtruth/task3"
def kwrec(t,kws): t=(t or "").lower(); return sum(1 for k in kws if k in t)/len(kws) if kws else 0
POS=["pos0","pos25","pos50","pos75","pos100"]
def load(f):
    p=os.path.join(T3,f)
    if not os.path.exists(p): return None
    d=json.load(open(p)); return d["results"] if isinstance(d,dict) else d
print("=== M71 长上下文位置效应细扫 + 跨模型(dep-recall, judge-independent)===")
print(f"{'model':12}" + "".join(f"{p:>9}" for p in POS))
curves={}
for f,name in [("scores_poslong_coder.json","Coder-14B"),("scores_poslong_qwen.json","Qwen-14B")]:
    res=load(f)
    if not res: print(f"{name}: (missing)"); continue
    row={p:[] for p in POS}
    for r in res:
        for p in POS: row[p].append(kwrec(r["ans"].get(p,""), r["keywords"]))
    curves[name]={p:sum(row[p])/len(row[p]) for p in POS}
    print(f"{name:12}" + "".join(f"{curves[name][p]:>9.3f}" for p in POS))
print("\n判读(每模型):")
for name,c in curves.items():
    start=c["pos0"]; mid=c["pos50"]; end=c["pos100"]
    litm = mid - (start+end)/2   # <0 => 中间最差(经典LITM)
    rec = end - start            # >0 => recency(末尾>开头)
    shape = "recency(末尾>开头)" if rec>0.03 else ("LITM(中间最差)" if litm<-0.03 else "平")
    print(f"  {name}: 开头{start:.3f} 中{mid:.3f} 末尾{end:.3f} | recency(末-开)={rec:+.3f} LITM(中-端均)={litm:+.3f} → {shape}")
print("\n机理(诚实,任务依赖性):本任务是'找一条权威依赖信息'(单点检索)非'综合多处'——recency 可能是该任务特性;")
print("不过度推广到所有长上下文场景。跨模型若都 recency → 该任务上稳健;若分歧 → 模型依赖,如实标。")
