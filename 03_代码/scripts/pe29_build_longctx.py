"""
M66 (CPU): build long-context-loss DIAGNOSIS instances. The authoritative dependency
card (containing the answer) is PRESENT in every condition; irrelevant werkzeug code
dilutes / pushes it away. Conditions: short / mid / long x position{start,mid,end}.
Padding EXCLUDES the seed file and any file matching a gold keyword, so the answer
appears ONLY in the card (isolates dilution, not info-absence). judge-independent gold.
"""
import json, os, re
WZ=r"D:/claude/49/repos/werkzeug"; DATA=r"D:/claude/49/data"; T3=r"D:/claude/59/pilot_devtruth/task3"
# werkzeug file contents
files={}
for dp,_,fns in os.walk(WZ):
    for fn in fns:
        if fn.endswith(".py"):
            rel=os.path.relpath(os.path.join(dp,fn),WZ).replace("\\","/")
            try: files[rel]=open(os.path.join(dp,fn),encoding="utf-8",errors="replace").read()
            except Exception: pass
allrel=sorted(files)

recs=[]
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    if r.get("judge",{}).get("type")=="keyword_all": recs.append(r)

MID_CHARS=16000; LONG_CHARS=44000
def card_for(r):
    kws=r["judge"]["keywords"]
    seed=(r.get("expected_sources") or ["(该文件)"])[0]
    return (f"[依赖图卡片 — 权威,回答时以此为准]\n"
            f"问题相关文件: {seed}\n"
            f"与本问题相关的依赖关系(项目内):{', '.join(kws)}\n"
            f"(以上为静态分析得到的权威依赖清单)")
def padding(seed, kws, n_chars):
    seed_bn=os.path.basename(seed)
    pool=[rel for rel in allrel
          if os.path.basename(rel)!=seed_bn
          and not any(k.lower() in rel.lower() for k in kws)]  # exclude answer-bearing files
    out=[]; tot=0
    for rel in pool:
        c=f"# ==== {rel} ====\n"+files[rel]
        out.append(c); tot+=len(c)
        if tot>=n_chars: break
    return "".join(out)[:n_chars]

insts=[]
for r in recs:
    seed=(r.get("expected_sources") or ["x.py"])[0]; kws=r["judge"]["keywords"]
    card=card_for(r); pad_mid=padding(seed,kws,MID_CHARS); pad_long=padding(seed,kws,LONG_CHARS)
    half=len(pad_long)//2
    conds={
        "short":      card,
        "mid":        pad_mid+"\n\n"+card,
        "long_start": card+"\n\n"+pad_long,
        "long_mid":   pad_long[:half]+"\n\n"+card+"\n\n"+pad_long[half:],
        "long_end":   pad_long+"\n\n"+card,
    }
    insts.append({"id":r["id"],"question":r["question"],"keywords":[k.lower() for k in kws],
                  "category":r["category"],"contexts":conds})
json.dump(insts, open(os.path.join(T3,"instances_longctx.json"),"w"), indent=1)
import statistics
print(f"instances={len(insts)}")
for c in ["short","mid","long_start"]:
    print(f"  {c}: avg chars={statistics.mean(len(i['contexts'][c]) for i in insts):.0f}")
print("answer present ONLY in card (padding excludes seed + gold-keyword files); tests dilution/position, not info-absence.")
