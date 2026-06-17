"""
M68 (超额, CPU, judge-independent): quantify how cross-encoder rerank MASKS embedding
quality differences. 3 embeddings (zh worst / MiniLM mid / en best) x rerank {off, on}.
Corpus = 52 werkzeug structural cards; queries = 56; gold = seed file (expected_sources).
rerank: embedding top-N candidate pool -> bge-reranker-base re-score -> top-K.
Mechanism: also report each embedding's Recall@N (candidate-pool ceiling rerank can reach).
"""
import os, re, json, ast
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY","1")
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
WZ=r"D:/claude/49/repos/werkzeug"; DATA=r"D:/claude/49/data"
card={}
for dp,_,fns in os.walk(WZ):
    for fn in fns:
        if not fn.endswith(".py"): continue
        rel=os.path.relpath(os.path.join(dp,fn),WZ).replace("\\","/")
        try: src=open(os.path.join(dp,fn),encoding="utf-8",errors="replace").read()
        except Exception: continue
        imps=[]; classes=[]; defs=[]
        try:
            for n in ast.walk(ast.parse(src)):
                if isinstance(n,ast.ImportFrom) and n.module: imps.append(n.module)
                elif isinstance(n,ast.Import):
                    for a in n.names: imps.append(a.name)
                elif isinstance(n,ast.ClassDef): classes.append(n.name)
                elif isinstance(n,ast.FunctionDef): defs.append(n.name)
        except Exception: pass
        card[rel]=f"File path: {rel}\nImports: {', '.join(imps[:25])}\nClasses: {', '.join(classes[:20])}\nFunctions: {', '.join(defs[:25])}"
rel=sorted(card); texts=[card[r] for r in rel]
queries=[]; golds=[]
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    es=r.get("expected_sources") or []
    g=set(rp for rp in rel for s in es if rp==s or rp.endswith("/"+s) or os.path.basename(rp)==os.path.basename(s))
    if g: queries.append(r["question"]); golds.append(g)
KS=[1,5,10]; N_POOL=30
reranker=CrossEncoder(r"D:/claude/49/models/bge-reranker-base")
def emb_order(m):
    ce=m.encode(texts,normalize_embeddings=True,show_progress_bar=False)
    qe=m.encode(queries,normalize_embeddings=True,show_progress_bar=False)
    sims=np.array(qe)@np.array(ce).T
    return [[rel[j] for j in np.argsort(-sims[i])] for i in range(len(queries))]
def score(orders):
    out={k:0 for k in KS}; mrr=0
    for i,g in enumerate(golds):
        o=orders[i]; f=next((r+1 for r,rp in enumerate(o) if rp in g),None)
        if f: mrr+=1/f
        for k in KS: out[k]+= any(rp in g for rp in o[:k])
    n=len(golds); return {k:out[k]/n for k in KS}, mrr/n
def recall_at(orders, N):
    return sum(any(rp in golds[i] for rp in orders[i][:N]) for i in range(len(golds)))/len(golds)
def rerank(orders):
    new=[]
    for i,o in enumerate(orders):
        pool=o[:N_POOL]
        scores=reranker.predict([(queries[i], card[rp]) for rp in pool])
        new.append([rp for _,rp in sorted(zip(scores,pool),key=lambda x:-x[0])] + o[N_POOL:])
    return new

MODELS=[("zh(最差,错语言)",r"D:/claude/49/models/bge-small-zh-v1.5"),
        ("MiniLM(中档)","sentence-transformers/all-MiniLM-L6-v2"),
        ("en(最好)","BAAI/bge-small-en-v1.5")]
print(f"=== M68 rerank × embedding 掩盖效应(judge-independent, n={len(queries)}, pool N={N_POOL})===")
print(f"{'embedding':18}{'R@5_off':>10}{'R@5_on':>10}{'MRR_off':>10}{'MRR_on':>10}{'R@30(候选池)':>14}")
res={}
for name,mid in MODELS:
    m=SentenceTransformer(mid); orders=emb_order(m)
    roff,moff=score(orders); ron,mon=score(rerank(orders)); r30=recall_at(orders,N_POOL)
    res[name]=dict(off=roff[5],on=ron[5],mrroff=moff,mrron=mon,r30=r30)
    print(f"{name:18}{roff[5]:>10.3f}{ron[5]:>10.3f}{moff:>10.3f}{mon:>10.3f}{r30:>14.3f}")
zh=res["zh(最差,错语言)"]; en=res["en(最好)"]
print(f"\n=== 掩盖度量化 ===")
print(f"  rerank OFF: zh R@5 {zh['off']:.3f} vs en {en['off']:.3f} → 差距 {en['off']-zh['off']:+.3f}（embedding 质量全传导）")
print(f"  rerank ON : zh R@5 {zh['on']:.3f} vs en {en['on']:.3f} → 差距 {en['on']-zh['on']:+.3f}（被掩盖）")
comp = (en['off']-zh['off'])/(en['on']-zh['on']) if (en['on']-zh['on'])!=0 else float('inf')
print(f"  掩盖度:rerank 把 {en['off']-zh['off']:.3f} 的差距压到 {en['on']-zh['on']:.3f}（压缩 {comp:.1f}×）")
print(f"  机理边界:rerank 救弱 embedding 的上限 = 候选池召回 R@{N_POOL}（zh {zh['r30']:.3f}）——正确卡片进了池子才救得回；进不去就救不了。")
json.dump(res, open(r"D:/claude/59/pilot_devtruth/out/pe32_rerank_masking.json","w"))
