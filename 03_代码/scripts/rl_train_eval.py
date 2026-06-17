"""M24-25:用ppl-reward弱监督训RL检索器 + werkzeug四方对照(Recall@K/MRR,纯CPU)。
RL检索器 vs 现成bge vs M14对比学习 vs 静态分析(卡片即精确依赖,作oracle参照)。
"""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/"src"))
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
import warnings; warnings.filterwarnings("ignore")
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import numpy as np

# 1) ppl弱监督训练样本:anchor=query, positive=ppl-best卡片
ppl=json.load(open(ROOT/"results"/"rl_ppl.json",encoding="utf-8"))
qs={x["qid"]:x for x in [json.loads(l) for l in open(ROOT/"data"/"rl_queries.jsonl",encoding="utf-8")]}
examples=[]
for r in ppl["results"]:
    q=qs[r["qid"]]; best=r["argmin"]
    examples.append(InputExample(texts=[q["query"], q["candidates"][best]["text"]]))
print(f"RL训练样本(ppl弱监督正例){len(examples)}条")
model=SentenceTransformer(str(ROOT/"models"/"bge-small-zh-v1.5"), device="cpu")
loss=losses.MultipleNegativesRankingLoss(model)
model.fit([(DataLoader(examples,shuffle=True,batch_size=8),loss)], epochs=3, warmup_steps=5, show_progress_bar=False)
model.save(str(ROOT/"models"/"bge-small-rl"))
print("RL检索器已训练 -> models/bge-small-rl")

# 2) werkzeug 评测:forward_dep 查询,gold卡片=焦点文件卡片;候选=全部werkzeug文件卡片
from repomind_lab.chunking import build_chunks
wz=ROOT/"repos"/"werkzeug"
fcards={}
for c in build_chunks(wz, strategy="function", include_graph_cards=True):
    if getattr(c,"kind",None)=="graph" and str(c.chunk_id).startswith("graph:file:"):
        fcards[c.source]=c.text
ids=list(fcards); texts=[fcards[i] for i in ids]; id2i={i:k for k,i in enumerate(ids)}
cs=[json.loads(l) for l in open(ROOT/"data"/"testcases_werkzeug.jsonl",encoding="utf-8") if l.strip() and not l.startswith("//")]
evalq=[(c["question"],c["expected_sources"][0]) for c in cs if c["category"] in ("forward_dep","reverse_dep") and c.get("expected_sources") and c["expected_sources"][0] in id2i]
print(f"werkzeug 评测查询 {len(evalq)}(forward/reverse,gold卡片在池)")

def eval_retriever(path,label):
    m=SentenceTransformer(path, device="cpu")
    emb=m.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    qe=m.encode([q for q,_ in evalq], normalize_embeddings=True, show_progress_bar=False)
    r5=mrr=0
    for k,(q,gold) in enumerate(evalq):
        sims=emb@qe[k]; rank=list(np.argsort(-sims))
        gi=id2i[gold]; pos=rank.index(gi)
        if pos<5: r5+=1
        mrr+=1/(pos+1)
    n=len(evalq)
    print(f"  {label:<22} Recall@5={r5/n:.3f}  MRR={mrr/n:.3f}")

print("\n=== werkzeug 检索四方对照(纯embedding,gold依赖卡片)===")
eval_retriever(str(ROOT/"models"/"bge-small-zh-v1.5"), "现成bge-small")
eval_retriever(str(ROOT/"models"/"bge-small-zh-ft"), "M14对比学习")
eval_retriever(str(ROOT/"models"/"bge-small-rl"), "RL(ppl弱监督)")
print("  静态分析依赖检索        Recall@5=1.000  MRR=1.000  (oracle:卡片即精确依赖,构造保证命中)")
