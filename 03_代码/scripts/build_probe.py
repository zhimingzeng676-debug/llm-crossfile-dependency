"""M35任务一:Coder裁判偏好探针。构造已知正确性的答案变体,判分vs客观真值测偏好。
变体:correct-concise/correct-verbose/correct-hedged/wrong-confident。客观真值=是否含gold关键词。
"""
import json,sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results"/"probe"; OUT.mkdir(parents=True,exist_ok=True)
cs={json.loads(l)["id"]:json.loads(l) for l in open(ROOT/"data"/"testcases_werkzeug.jsonl",encoding="utf-8") if l.strip() and not l.startswith("//")}
# 取5个forward_dep(gold清晰)
fwd=[c for c in cs.values() if c["category"]=="forward_dep" and 3<=len(c["judge"].get("keywords",[]))<=5][:5]
bundle=[]; runs0=[]
PAD="顺便说明,代码依赖分析对理解大型项目的架构非常重要,合理的模块划分能降低耦合、提升可维护性,静态分析工具能帮助开发者把握全局结构,这是软件工程的基础实践。"
for c in fwd:
    kws=c["judge"]["keywords"]; q=c["question"]; cid=c["id"]
    correct=", ".join(kws)  # 含全部gold关键词=客观对
    wrong="它依赖了 wsgi, http, json, base64 这几个模块"  # 故意错(不含gold)
    variants={
        "concise": f"它依赖:{correct}。",
        "verbose": f"经过分析,该文件直接 import 了以下本仓库内模块:{correct}。{PAD}{PAD}",
        "hedged": f"我不太确定,但根据我的理解,它可能依赖了 {correct} 这些模块,具体还需核对源码。",
        "wrongconf": f"该文件明确依赖以下模块:{wrong}。这是确定的。",
    }
    for v,ans in variants.items():
        vid=f"{cid}-{v}"
        bundle.append({"id":vid,"category":c["category"],"difficulty":"medium","question":q,
                       "gold":", ".join(kws),"notes":c.get("notes","")[:80],
                       "obj_correct": v!="wrongconf"})  # 客观真值
        runs0.append({"id":vid,"difficulty":"medium","category":c["category"],"answer":ans})
json.dump(bundle,open(OUT/"probe_bundle.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump({"n_runs":1,"runs":[runs0]},open(OUT/"probe_answers.json","w",encoding="utf-8"),ensure_ascii=False)
print(f"探针:{len(fwd)}问题×4变体={len(bundle)}答案(concise/verbose/hedged客观对,wrongconf客观错)")
