"""M21:大项目检索可行性 —— 1456卡片池下,正确卡片能否被检索到(Recall@k vs 深度)。
BM25 + bge-small语义 混合(RRF)+ cross-encoder rerank。输出 Recall@k 表 + full/baseline bundle。
"""
import json, sys, re, math, time
from pathlib import Path
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
CPY=ROOT/"results"/"cpy"
cards=[json.loads(l) for l in open(CPY/"cards.jsonl",encoding="utf-8")]
cases=json.load(open(CPY/"cpy_cases.json",encoding="utf-8"))
ids=[c["id"] for c in cards]; texts=[c["text"] for c in cards]; id2idx={c["id"]:i for i,c in enumerate(cards)}
print(f"卡片池 {len(cards)}, 用例 {len(cases)}")

# ---- BM25 ----
def tok(s):
    s=s.lower(); parts=re.split(r'[^a-z0-9_]+', s)
    out=[]
    for p in parts:
        if p: out.append(p); out+= [x for x in p.split('_') if x]
    return out
doc_tok=[tok(t) for t in texts]
df=Counter();
for d in doc_tok:
    for w in set(d): df[w]+=1
N=len(doc_tok); avgdl=sum(len(d) for d in doc_tok)/N
idf={w:math.log(1+(N-n+0.5)/(n+0.5)) for w,n in df.items()}
def bm25(q):
    qt=tok(q); sc=[0.0]*N
    for i,d in enumerate(doc_tok):
        tf=Counter(d); dl=len(d); s=0.0
        for w in qt:
            if w in tf:
                f=tf[w]; s+=idf.get(w,0)*f*2.5/(f+1.5*(0.25+0.75*dl/avgdl))
        sc[i]=s
    return sc

# ---- 语义(bge-small)----
t0=time.time()
from sentence_transformers import SentenceTransformer
import numpy as np
model=SentenceTransformer(str(ROOT/"models"/"bge-small-zh-v1.5"), device="cpu")
emb=model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
print(f"[{time.time()-t0:.0f}s] 卡片向量化完成 {emb.shape}")

def rrf(rank_lists, k=60):
    sc=defaultdict(float)
    for rl in rank_lists:
        for r,idx in enumerate(rl): sc[idx]+=1.0/(k+r+1)
    return sorted(sc, key=lambda i:-sc[i])

# ---- cross-encoder rerank ----
from sentence_transformers import CrossEncoder
ce=CrossEncoder(str(ROOT/"models"/"bge-reranker-base"), device="cpu")

KS=[8,20,50,80,200,500]
recall=defaultdict(lambda: defaultdict(int)); tot=defaultdict(int)
full_bundle=[]; base_bundle=[]
SC_FULL=("你是一个代码仓库依赖分析助手。请仅依据以下检索到的依赖卡片回答问题。"
         "如果卡片里没有答案,请明确说\"根据给定卡片没有找到\",不要臆造。\n\n")
SC_BASE=("你是一个代码仓库依赖分析助手。请根据你对 CPython 的了解回答下面的跨文件依赖问题。"
         "如果不确定请明确说\"不确定\",不要臆造。\n\n")
qv=model.encode([c["question"] for c in cases], normalize_embeddings=True)
for ci,c in enumerate(cases):
    gold=c["gold_card"]; gi=id2idx.get(gold)
    bm=bm25(c["question"]);
    bm_rank=sorted(range(N), key=lambda i:-bm[i])
    sem=(emb@qv[ci]); sem_rank=sorted(range(N), key=lambda i:-sem[i])
    hyb=rrf([bm_rank,sem_rank])
    pos=hyb.index(gi) if gi in hyb else 10**9
    cat=c["category"]; tot[cat]+=1
    for k in KS:
        if pos<k: recall[cat][k]+=1
    # rerank top-80 hybrid -> top-8 into prompt
    cand=hyb[:80]
    ce_scores=ce.predict([(c["question"], texts[i]) for i in cand])
    reranked=[cand[i] for i in sorted(range(len(cand)), key=lambda j:-ce_scores[j])]
    top=reranked[:8]
    cardtxt="\n\n".join(texts[i] for i in top)
    full_bundle.append({"id":c["id"],"category":cat,"difficulty":"medium","question":c["question"],
        "gold":c["gold"],"notes":"(CPython大项目,检索top8)","gen_prompt":SC_FULL+cardtxt+f"\n\n问题:{c['question']}\n请直接回答。",
        "gold_in_top8": gi in top, "gold_hybrid_pos": pos})
    base_bundle.append({"id":c["id"],"category":cat,"difficulty":"medium","question":c["question"],
        "gold":c["gold"],"notes":"(CPython大项目)","gen_prompt":SC_BASE+f"问题:{c['question']}\n请直接回答。"})

print("\n=== 检索可行性:Recall@k(gold卡片在混合检索top-k)按类型 ===")
print(f"{'类型':<12}{'n':>3} "+" ".join(f"@{k}".rjust(6) for k in KS))
for cat in tot:
    print(f"{cat:<12}{tot[cat]:>3} "+" ".join(f"{recall[cat][k]/tot[cat]:.2f}".rjust(6) for k in KS))
allk={k:sum(recall[cat][k] for cat in tot)/sum(tot.values()) for k in KS}
print(f"{'全体':<12}{sum(tot.values()):>3} "+" ".join(f"{allk[k]:.2f}".rjust(6) for k in KS))
git8=sum(1 for b in full_bundle if b["gold_in_top8"])
print(f"\nrerank后 gold 进入 top-8(喂给模型)的比例:{git8}/{len(full_bundle)} = {git8/len(full_bundle):.1%}")
json.dump(full_bundle, open(CPY/"bundle_cpy_full.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(base_bundle, open(CPY/"bundle_cpy_baseline.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"recall":{c:dict(recall[c]) for c in recall},"tot":dict(tot),"allk":allk,"gold_in_top8":git8},
          open(CPY/"retrieval_feasibility.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("bundle_cpy_full/baseline.json 已存")
