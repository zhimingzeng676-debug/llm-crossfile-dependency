"""
M69 (CPU): build System-Prompt-ablation instances. context = seed file SOURCE
(contains the real imports = answer for forward-dep). Ask the dependency question.
System-on (anti-hallucination constraint) vs System-off. Hallucination = predicted .py
file NOT appearing in the provided context source (made up). judge-independent gold.
Uses forward_dep + inheritance + symbol cases (answer derivable from seed source).
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
def find(seed):
    bn=os.path.basename(seed)
    for rel in files:
        if rel==seed or rel.endswith("/"+seed) or os.path.basename(rel)==bn: return rel
    return None
insts=[]
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    if r.get("judge",{}).get("type")!="keyword_all": continue
    seed=(r.get("expected_sources") or [None])[0]
    rel=find(seed) if seed else None
    if not rel: continue
    src=files[rel][:6000]
    insts.append({"id":r["id"],"question":r["question"],"keywords":[k.lower() for k in r["judge"]["keywords"]],
                  "category":r["category"],"context":f"# 文件 {rel} 的源码:\n{src}"})
json.dump(insts, open(os.path.join(T3,"instances_sysabl.json"),"w"), indent=1)
print(f"sysabl instances={len(insts)}")
