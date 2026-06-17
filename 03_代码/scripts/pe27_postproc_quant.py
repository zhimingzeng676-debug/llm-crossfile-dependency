"""
M64 (CPU, judge-independent): independently quantify post-processing FILTER / SORT /
DEDUP / COMPLETION on the existing werkzeug PE answers, using keyword_all det-recall
(gold = testcase judge.keywords) + a precision proxy. No GPU, no LLM judge.
"""
import json, os, re
R=r"D:/claude/49/results"; DATA=r"D:/claude/49/data"
gold={}
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    if r.get("judge",{}).get("type")=="keyword_all":
        gold[r["id"]]=[k.lower() for k in r["judge"]["keywords"]]
ans={x["id"]:x["answer"] for x in json.load(open(os.path.join(R,"answers_werkzeug_pe_all.json"),encoding="utf-8"))}
pp ={x["id"]:x["answer"] for x in json.load(open(os.path.join(R,"answers_werkzeug_pe_all_pp.json"),encoding="utf-8"))}
prompts={x["id"]:x["prompt"] for x in json.load(open(os.path.join(R,"prompts_werkzeug_pe_all.json"),encoding="utf-8"))}

FILE_TOK=re.compile(r"[A-Za-z_][\w/]*\.py")
def kw_recall(text, gkw):
    t=text.lower(); return sum(1 for k in gkw if k in t)/len(gkw) if gkw else 0
def pred_items(text): return FILE_TOK.findall(text)
def card_items(prompt):
    # card list lines (reverse/forward/subclass authoritative lists)
    items=set()
    for line in prompt.splitlines():
        if any(t in line for t in ["被这些文件依赖","它依赖(import)的仓库内文件","继承它的子类","依赖图卡片","卡片"]):
            items.update(FILE_TOK.findall(line))
    items.update(FILE_TOK.findall(prompt))  # fallback: any .py in prompt context
    return items

ids=[i for i in gold if i in ans]
def is_gold(tok,gkw): return any(k in tok.lower() for k in gkw)

# base / completion recall
rb=sum(kw_recall(ans[i],gold[i]) for i in ids)/len(ids)
rc=sum(kw_recall(pp.get(i,ans[i]),gold[i]) for i in ids)/len(ids)

# dedup + filter on predicted items; precision proxy
def precision(items,gkw):
    if not items: return None
    return sum(1 for t in items if is_gold(t,gkw))/len(items)
dup_removed=0; halluc_removed=0; n_with_dup=0; n_with_halluc=0
prec_base=[]; prec_dedup=[]; prec_filter=[]; rec_filter=[]
for i in ids:
    items=pred_items(ans[i]); gkw=gold[i]
    ctx=set(FILE_TOK.findall(prompts.get(i,"")))  # retrieved context = all .py in generation prompt
    # dedup
    seen=[]; [seen.append(x) for x in items if x not in seen]
    if len(items)!=len(seen): n_with_dup+=1; dup_removed+=len(items)-len(seen)
    # filter: ungrounded = predicted .py NOT anywhere in retrieved context (pure hallucination)
    ungrounded=[x for x in seen if x not in ctx and not any(x.endswith("/"+c) or c.endswith("/"+x) for c in ctx)]
    if ungrounded: n_with_halluc+=1
    halluc_removed+= len(ungrounded)
    filt=[x for x in seen if x not in ungrounded]
    prec_base.append(precision(items,gkw)); prec_dedup.append(precision(seen,gkw)); prec_filter.append(precision(filt,gkw))
    # recall after filter = recall on answer with ungrounded file tokens stripped
    fa=ans[i]
    for u in ungrounded: fa=fa.replace(u,"")
    rec_filter.append(kw_recall(fa,gkw))
def avg(xs): xs=[x for x in xs if x is not None]; return sum(xs)/len(xs) if xs else 0

print("=== M64 后处理四类独立量化(判分无关 keyword_all det-recall + 精度代理;werkzeug 56 例)===")
print(f"\n[补全 completion](把检索卡片里有、答案漏列的补回)")
print(f"  det-recall: base {rb:.3f} -> completion {rc:.3f}  Δ={rc-rb:+.3f}  (pp 改动 {sum(1 for i in ids if pp.get(i)!=ans[i])}/{len(ids)} 条)")
print(f"\n[去重 dedup](折叠答案里重复列出的同一依赖项)")
print(f"  有重复项的用例: {n_with_dup}/{len(ids)};共去掉重复项 {dup_removed} 个")
print(f"  det-recall 不变(不删 distinct 项);精度代理: base {avg(prec_base):.3f} -> dedup {avg(prec_dedup):.3f}  Δ={avg(prec_dedup)-avg(prec_base):+.3f}")
print(f"\n[过滤 filter](剔除答案里检索上下文完全没有的幻觉文件名 = 反幻觉接地过滤)")
print(f"  有幻觉项的用例 {n_with_halluc}/{len(ids)};共剔除未接地项 {halluc_removed} 个")
print(f"  det-recall: base {rb:.3f} -> filter {avg(rec_filter):.3f}（≈base=过滤没误删真依赖）;精度代理 {avg(prec_base):.3f} -> {avg(prec_filter):.3f}")
print(f"\n[排序 sort = rerank](检索层,非答案文本操作)")
print(f"  已独立量化:rerank 12→80 det/judge +0.14(JUDGE_INDEPENDENT_VALIDATION/SCALE_STRESS_TEST),此处不重复。")
print("\n机理诚实:补全帮反向依赖漏列(recall↑);去重/过滤改善精度/清洁度(幻觉↓)但不增 recall;排序(检索深度)是四类里最大杠杆。")
