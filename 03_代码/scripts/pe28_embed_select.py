"""
M65 (CPU, judge-independent): systematic Embedding selection comparison on the
werkzeug dependency-CARD retrieval task. corpus = one structural card per .py file;
query = the 56 dependency questions; gold = the seed file (expected_sources).
Metrics: Recall@{1,5,10,20} + MRR (rank-based, deterministic — no LLM judge).
Compares the project's current bge-small-zh-v1.5 vs other off-the-shelf embeddings.
HONEST framing: this is the SEMANTIC layer; the deterministic dependency-card retrieval
(+rerank, Recall@5 0.95 full-stack) dominates — embedding is a SECONDARY knob.
"""
import os, re, json, ast
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY","1")
import numpy as np
from sentence_transformers import SentenceTransformer

WZ=r"D:/claude/49/repos/werkzeug"; DATA=r"D:/claude/49/data"

# ---- build structural cards (one per .py file, repo-relative path) ----
cards={}  # relpath -> card text
for dp,_,fns in os.walk(WZ):
    for fn in fns:
        if not fn.endswith(".py"): continue
        fp=os.path.join(dp,fn); rel=os.path.relpath(fp,WZ).replace("\\","/")
        try: src=open(fp,encoding="utf-8",errors="replace").read()
        except Exception: continue
        imps=[]; defs=[]; classes=[]
        try:
            t=ast.parse(src)
            for n in ast.walk(t):
                if isinstance(n,ast.ImportFrom) and n.module: imps.append(n.module)
                elif isinstance(n,ast.Import):
                    for a in n.names: imps.append(a.name)
                elif isinstance(n,ast.FunctionDef): defs.append(n.name)
                elif isinstance(n,ast.ClassDef): classes.append(n.name)
        except Exception: pass
        card=(f"File path: {rel}\n"
              f"Imports: {', '.join(imps[:25])}\n"
              f"Classes: {', '.join(classes[:20])}\n"
              f"Functions: {', '.join(defs[:25])}")
        cards[rel]=card
relpaths=sorted(cards); card_texts=[cards[r] for r in relpaths]
print(f"corpus: {len(relpaths)} werkzeug card-docs")

# ---- queries + gold (seed file = expected_sources) ----
queries=[]; golds=[]
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    es=r.get("expected_sources") or []
    gold=set()
    for s in es:
        # match to a corpus relpath (suffix)
        for rp in relpaths:
            if rp==s or rp.endswith("/"+s) or os.path.basename(rp)==os.path.basename(s): gold.add(rp)
    if gold:
        queries.append(r["question"]); golds.append(gold)
print(f"queries with resolvable gold: {len(queries)}/56")

MODELS=[
    ("bge-small-zh-v1.5(当前)", r"D:/claude/49/models/bge-small-zh-v1.5"),
    ("all-MiniLM-L6-v2(通用英文)", "sentence-transformers/all-MiniLM-L6-v2"),
    ("bge-small-en-v1.5(英文bge)", "BAAI/bge-small-en-v1.5"),
    ("st-codesearch-distilroberta(代码)", "flax-sentence-embeddings/st-codesearch-distilroberta-base"),
]
KS=[1,5,10,20]
def metrics(qemb, cemb):
    sims=qemb@cemb.T  # cos (normalized)
    rec={k:0 for k in KS}; mrr=0.0
    for i,g in enumerate(golds):
        order=np.argsort(-sims[i])
        ranked=[relpaths[j] for j in order]
        first=next((r+1 for r,rp in enumerate(ranked) if rp in g), None)
        if first: mrr+=1.0/first
        for k in KS:
            if any(rp in g for rp in ranked[:k]): rec[k]+=1
    n=len(golds)
    return {k:rec[k]/n for k in KS}, mrr/n

print(f"\n{'embedding':38}" + "".join(f"R@{k:<5}" for k in KS) + "MRR")
results={}
for name,mid in MODELS:
    try:
        m=SentenceTransformer(mid)
        ce=m.encode(card_texts, normalize_embeddings=True, show_progress_bar=False)
        qe=m.encode(queries, normalize_embeddings=True, show_progress_bar=False)
        rec,mrr=metrics(np.array(qe),np.array(ce))
        results[name]=(rec,mrr)
        print(f"{name:38}" + "".join(f"{rec[k]:<7.3f}" for k in KS) + f"{mrr:.3f}")
    except Exception as e:
        print(f"{name:38} [skip: {str(e)[:60]}]")
json.dump({n:{"recall":r,"mrr":m} for n,(r,m) in results.items()},
          open(r"D:/claude/59/pilot_devtruth/out/pe28_embed_select.json","w"))
print("\nHONEST: this is the SEMANTIC retrieval layer. Full-stack deterministic card retrieval")
print("+ cross-encoder rerank reaches Recall@5 ~0.95 (EVALUATION_REPORT §3) — embedding选型 is a SECONDARY knob.")
