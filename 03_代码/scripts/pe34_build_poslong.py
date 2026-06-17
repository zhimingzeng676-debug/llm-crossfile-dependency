"""
M71 (CPU): build long-context POSITION-scan instances (finer than M66). Authoritative
card (answer) placed at fractional positions {0, 0.25, 0.5, 0.75, 1.0} within ~44k chars
of irrelevant werkzeug code. Tests recency vs lost-in-the-middle. Padding excludes seed +
gold-keyword files (answer only in card). Reuses M66 card/padding logic. judge-independent.
"""
import json, os
WZ=r"D:/claude/49/repos/werkzeug"; DATA=r"D:/claude/49/data"; T3=r"D:/claude/59/pilot_devtruth/task3"
files={}
for dp,_,fns in os.walk(WZ):
    for fn in fns:
        if fn.endswith(".py"):
            rel=os.path.relpath(os.path.join(dp,fn),WZ).replace("\\","/")
            try: files[rel]=open(os.path.join(dp,fn),encoding="utf-8",errors="replace").read()
            except Exception: pass
allrel=sorted(files)
LONG=44000
def card_for(r):
    kws=r["judge"]["keywords"]; seed=(r.get("expected_sources") or ["(该文件)"])[0]
    return (f"[依赖图卡片 — 权威,回答时以此为准]\n问题相关文件: {seed}\n"
            f"与本问题相关的依赖关系(项目内):{', '.join(kws)}\n(以上为静态分析得到的权威依赖清单)")
def padding(seed,kws,n):
    bn=os.path.basename(seed)
    pool=[r for r in allrel if os.path.basename(r)!=bn and not any(k.lower() in r.lower() for k in kws)]
    out=[]; tot=0
    for r in pool:
        c=f"# ==== {r} ====\n"+files[r]; out.append(c); tot+=len(c)
        if tot>=n: break
    return "".join(out)[:n]
POS=[0.0,0.25,0.5,0.75,1.0]
insts=[]
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    if r.get("judge",{}).get("type")!="keyword_all": continue
    seed=(r.get("expected_sources") or ["x.py"])[0]; kws=r["judge"]["keywords"]
    card=card_for(r); pad=padding(seed,kws,LONG)
    ctx={}
    for p in POS:
        cut=int(len(pad)*p)
        ctx[f"pos{int(p*100)}"]=pad[:cut]+"\n\n"+card+"\n\n"+pad[cut:]
    insts.append({"id":r["id"],"question":r["question"],"keywords":[k.lower() for k in kws],
                  "category":r["category"],"contexts":ctx})
json.dump(insts, open(os.path.join(T3,"instances_poslong.json"),"w"), indent=1)
print(f"poslong instances={len(insts)}; positions={['pos'+str(int(p*100)) for p in POS]}")
