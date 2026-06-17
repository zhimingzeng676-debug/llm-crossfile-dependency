"""M24:RLCoder式RL检索器训练数据(隔离项目,werkzeug留出)。
每查询=候选池(含静态分析正确卡片+干扰)+目标(依赖答案)。供GPU算ppl-reward选正例。
输出 data/rl_queries.jsonl: {qid,query,target,candidates:[{id,text}],static_idx}
"""
import json, sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/"src"))
sys.stdout.reconfigure(encoding="utf-8")
from repomind_lab.chunking import build_chunks
from repomind_lab.repo_parser import parse_repo
ROOT=Path(__file__).resolve().parent.parent
TRAIN=["flask","click","jinja2","requests"]
random.seed(42)

def file_cards(rp):
    fcards={}
    for c in build_chunks(rp, strategy="function", include_graph_cards=True):
        if getattr(c,"kind",None)=="graph" and str(c.chunk_id).startswith("graph:file:"):
            fcards[c.source]=c.text
    return fcards

out=[]
for repo in TRAIN:
    rp=ROOT/"repos"/repo
    if not rp.exists(): continue
    g=parse_repo(rp); fcards=file_cards(rp)
    import collections
    deps=collections.defaultdict(set)
    for a,b in g.import_edges(): deps[a].add(b)
    files=[f for f in fcards if 2<=len(deps.get(f,()))<=6]
    random.shuffle(files)
    for f in files[:10]:
        dep_names=sorted({Path(x).name for x in deps[f]})
        target="该文件依赖的仓库内模块: "+", ".join(dep_names)
        # 候选池:正确=f自身卡片(含依赖列表),干扰=其他文件卡片
        others=[o for o in fcards if o!=f]; random.shuffle(others)
        cand=[{"id":f,"text":fcards[f]}]+[{"id":o,"text":fcards[o]} for o in others[:5]]
        random.shuffle(cand)
        sidx=next(i for i,c in enumerate(cand) if c["id"]==f)
        out.append({"qid":f"{repo}:{Path(f).name}","query":f"在 {repo} 中,{f} 这个文件直接依赖(import)了哪些仓库内的文件?",
                    "target":target,"candidates":cand,"static_idx":sidx})
(ROOT/"data"/"rl_queries.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in out),encoding="utf-8")
print(f"RL训练查询 {len(out)} 条(隔离项目,werkzeug留出),每条候选 {len(out[0]['candidates'])}")
print("样例:",out[0]["qid"],"| target:",out[0]["target"][:60],"| static_idx:",out[0]["static_idx"])
