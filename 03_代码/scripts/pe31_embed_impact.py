"""
M67 (CPU, judge-independent): does the wrong-language (zh) embedding change the
A-class conclusion "structured dependency cards >> raw-code/similarity retrieval"?
Re-run the semantic arm with the CORRECT (en) embedding. Same granularity (one doc per
file): card_doc = structured dependency card; code_doc = raw file content. Retrieve by
query, gold = seed file (expected_sources). Recall@K with zh vs en. Direction & magnitude.
"""
import os, re, json, ast
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY","1")
import numpy as np
from sentence_transformers import SentenceTransformer
WZ=r"D:/claude/49/repos/werkzeug"; DATA=r"D:/claude/49/data"
# build per-file card_doc and code_doc
card={}; code={}
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
        code[rel]=src[:2000]   # raw code (naive RAG arm), same per-file granularity
rel=sorted(card)
queries=[]; golds=[]
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    es=r.get("expected_sources") or []
    g=set(rp for rp in rel for s in es if rp==s or rp.endswith("/"+s) or os.path.basename(rp)==os.path.basename(s))
    if g: queries.append(r["question"]); golds.append(g)
KS=[1,5,10]
def recall(m, docs):
    ce=m.encode([docs[r] for r in rel],normalize_embeddings=True,show_progress_bar=False)
    qe=m.encode(queries,normalize_embeddings=True,show_progress_bar=False)
    sims=np.array(qe)@np.array(ce).T
    out={k:0 for k in KS}; mrr=0
    for i,g in enumerate(golds):
        order=[rel[j] for j in np.argsort(-sims[i])]
        f=next((r+1 for r,rp in enumerate(order) if rp in g),None)
        if f: mrr+=1/f
        for k in KS: out[k]+= any(rp in g for rp in order[:k])
    n=len(golds); return {k:out[k]/n for k in KS}, mrr/n
MODELS=[("zh(当前,错语言)",r"D:/claude/49/models/bge-small-zh-v1.5"),
        ("en(正确)","BAAI/bge-small-en-v1.5")]
print(f"=== M67 embedding 影响:结构化卡片检索 vs 原始代码检索(同粒度,n={len(queries)})===")
print(f"{'embedding':18}{'arm':14}{'R@1':>7}{'R@5':>7}{'R@10':>7}{'MRR':>7}")
out={}
for name,mid in MODELS:
    m=SentenceTransformer(mid)
    for arm,docs in [("依赖卡片",card),("原始代码",code)]:
        rec,mrr=recall(m,docs); out[(name,arm)]=(rec,mrr)
        print(f"{name:18}{arm:14}{rec[1]:>7.3f}{rec[5]:>7.3f}{rec[10]:>7.3f}{mrr:>7.3f}")
print("\n关键对比(R@5):")
for name,_ in MODELS:
    cr=out[(name,'依赖卡片')][0][5]; rr=out[(name,'原始代码')][0][5]
    print(f"  {name}: 卡片 {cr:.3f} vs 原始代码 {rr:.3f}  → 卡片-代码差距 {cr-rr:+.3f}")
print("\n判读:方向(卡片>代码)是否在正确 en embedding 下仍成立?差距幅度是否缩小?")
