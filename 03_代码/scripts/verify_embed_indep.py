# -*- coding: utf-8 -*-
"""独立复现(M75):embedding 选型 + rerank 掩盖。自己写自己算,不读项目结论。
corpus=werkzeug 每个 .py 一张结构卡;query=56 依赖问题;gold=expected_sources 对应文件(判分无关,排序指标)。
对比 bge-zh / bge-en / MiniLM / codesearch 的纯语义 R@K+MRR;再 rerank(bge-reranker-base)top-N 看 en-zh 差距压缩。"""
import os, json, ast
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

# 路径:testcases 用仓库内相对路径;werkzeug 源码 + 模型为外部依赖,经环境变量提供
# 外部依赖(clone 后需自备):WERKZEUG_SRC=werkzeug 源码目录;embedding/reranker 默认从 HuggingFace 拉取(需联网),
# 或设环境变量 BGE_ZH_PATH / RERANKER_PATH 指向本地模型。
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WZ = os.environ.get("WERKZEUG_SRC", "")  # 必填:werkzeug 源码目录(repo 不含第三方源码)
TC = os.path.join(_ROOT, "04_数据", "testcases_werkzeug.jsonl")
EMB = {
    "bge-zh(当前/中文)": os.environ.get("BGE_ZH_PATH", "BAAI/bge-small-zh-v1.5"),
    "bge-en(英文)": "BAAI/bge-small-en-v1.5",
    "MiniLM(通用英文)": "sentence-transformers/all-MiniLM-L6-v2",
    "codesearch(代码)": "flax-sentence-embeddings/st-codesearch-distilroberta-base",
}
RERANKER = os.environ.get("RERANKER_PATH", "BAAI/bge-reranker-base")
if not WZ or not os.path.isdir(WZ):
    raise SystemExit("请设置环境变量 WERKZEUG_SRC 指向 werkzeug 源码目录(repo 不含第三方源码)。")

# ---- corpus: 每个 .py 一张结构卡 ----
cards = {}
for dp, _, fns in os.walk(WZ):
    for fn in fns:
        if not fn.endswith(".py"): continue
        rel = os.path.relpath(os.path.join(dp, fn), WZ).replace("\\", "/")
        try: src = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
        except Exception: continue
        imps, defs, classes = [], [], []
        try:
            for n in ast.walk(ast.parse(src)):
                if isinstance(n, ast.ImportFrom) and n.module: imps.append(n.module)
                elif isinstance(n, ast.Import):
                    for a in n.names: imps.append(a.name)
                elif isinstance(n, ast.FunctionDef): defs.append(n.name)
                elif isinstance(n, ast.ClassDef): classes.append(n.name)
        except Exception: pass
        cards[rel] = f"File path: {rel}\nImports: {', '.join(imps[:25])}\nClasses: {', '.join(classes[:20])}\nFunctions: {', '.join(defs[:25])}"
relpaths = sorted(cards); card_texts = [cards[r] for r in relpaths]

# ---- queries + gold ----
queries, golds = [], []
for l in open(TC, encoding="utf-8"):
    l = l.strip().lstrip("﻿")
    if not l: continue
    try: r = json.loads(l)
    except Exception: continue
    g = set()
    for s in (r.get("expected_sources") or []):
        for rp in relpaths:
            if rp == s or rp.endswith("/" + s) or os.path.basename(rp) == os.path.basename(s): g.add(rp)
    if g: queries.append(r["question"]); golds.append(g)
n = len(golds)
print(f"corpus={len(relpaths)} cards | queries with gold={n}/56", flush=True)

KS = [1, 5, 10, 20, 30]
def emb_metrics(sims):
    rec = {k: 0 for k in KS}; mrr = 0.0; orders = []
    for i, g in enumerate(golds):
        order = np.argsort(-sims[i]); orders.append(order)
        ranked = [relpaths[j] for j in order]
        first = next((r + 1 for r, rp in enumerate(ranked) if rp in g), None)
        if first: mrr += 1.0 / first
        for k in KS:
            if any(rp in g for rp in ranked[:k]): rec[k] += 1
    return {k: rec[k] / n for k in KS}, mrr / n, orders

emb_res = {}; emb_orders = {}; emb_sims = {}
for name, mid in EMB.items():
    try:
        m = SentenceTransformer(mid)
        ce = np.array(m.encode(card_texts, normalize_embeddings=True, show_progress_bar=False))
        qe = np.array(m.encode(queries, normalize_embeddings=True, show_progress_bar=False))
        sims = qe @ ce.T
        rec, mrr, orders = emb_metrics(sims)
        emb_res[name] = (rec, mrr); emb_orders[name] = orders; emb_sims[name] = sims
        print(f"[emb] {name:24} R@5={rec[5]:.3f} R@10={rec[10]:.3f} MRR={mrr:.3f}", flush=True)
    except Exception as e:
        print(f"[emb] {name:24} SKIP {str(e)[:80]}", flush=True)

# ---- rerank 掩盖:top-30 池用 cross-encoder 重排,比 en/zh 的 MRR 差距 ----
POOL = 30
print(f"\n[rerank] 用 bge-reranker-base 重排各 embedding 的 top-{POOL} 池 ...", flush=True)
reranker = CrossEncoder(RERANKER, max_length=512)
def rerank_mrr(orders):
    mrr = 0.0
    for i, g in enumerate(golds):
        pool = [relpaths[j] for j in orders[i][:POOL]]
        pairs = [[queries[i], cards[rp]] for rp in pool]
        sc = reranker.predict(pairs, show_progress_bar=False)
        reranked = [rp for _, rp in sorted(zip(sc, pool), key=lambda x: -x[0])]
        first = next((r + 1 for r, rp in enumerate(reranked) if rp in g), None)
        if first: mrr += 1.0 / first
    return mrr / n

rr = {}
for name in ["bge-zh(当前/中文)", "bge-en(英文)"]:
    if name in emb_orders:
        on = rerank_mrr(emb_orders[name]); off = emb_res[name][1]
        rr[name] = (off, on)
        print(f"[rerank] {name:24} MRR off={off:.3f} -> on={on:.3f} (池内 gold R@{POOL}={emb_res[name][0][30]:.3f})", flush=True)

out = {"emb": {n: {"recall": r, "mrr": m} for n, (r, m) in emb_res.items()},
       "rerank": {n: {"mrr_off": o, "mrr_on": on} for n, (o, on) in rr.items()}}
if "bge-zh(当前/中文)" in rr and "bge-en(英文)" in rr:
    zo, zon = rr["bge-zh(当前/中文)"]; eo, eon = rr["bge-en(英文)"]
    gap_off = eo - zo; gap_on = eon - zon
    out["gap"] = {"off": round(gap_off, 4), "on": round(gap_on, 4),
                  "compression": round(gap_off / gap_on, 1) if gap_on else None}
    print(f"\n=== rerank 掩盖 ===")
    print(f"  无 rerank en-zh MRR 差距 = {gap_off:.3f}")
    print(f"  加 rerank en-zh MRR 差距 = {gap_on:.3f}")
    print(f"  压缩 = {gap_off/gap_on:.1f}x" if gap_on else "  压缩 = inf")
json.dump(out, open(os.path.join(_ROOT,"05_评测结果","verify_embed_result.json"), "w"), ensure_ascii=False, indent=1)
print("\nSAVED verify_embed_result.json"); print("DONE")
