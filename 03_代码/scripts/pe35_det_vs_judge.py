"""M70 (CPU): det-recall vs LLM-judge systematic comparison. Compute det-recall
(keyword_all) on existing werkzeug answer files; tabulate vs reported LLM-judge scores.
Honest: the two measure DIFFERENT things (structural recall vs comprehensive quality)."""
import json, os
R=r"D:/claude/49/results"; DATA=r"D:/claude/49/data"
gold={}
for l in open(os.path.join(DATA,"testcases_werkzeug.jsonl"),encoding="utf-8"):
    l=l.strip().lstrip("﻿")
    if not l: continue
    try: r=json.loads(l)
    except Exception: continue
    if r.get("judge",{}).get("type")=="keyword_all": gold[r["id"]]=[k.lower() for k in r["judge"]["keywords"]]
def detrecall(fname):
    p=os.path.join(R,fname)
    if not os.path.exists(p): return None
    ans={x["id"]:x["answer"] for x in json.load(open(p,encoding="utf-8"))}
    rs=[]
    for i,kws in gold.items():
        if i in ans:
            t=ans[i].lower(); rs.append(sum(1 for k in kws if k in t)/len(kws))
    return sum(rs)/len(rs) if rs else None
# (file, label, reported LLM-judge)  judge from EVALUATION/INSIGHT/PE_SOLUTION
ROWS=[
 ("answers_werkzeug_baseline_qwen.json","baseline(无卡片)", 0.19),
 ("answers_werkzeug_full_qwen.json","full RAG", 0.94),
 ("answers_werkzeug_pe_all.json","PE all", 0.79),
 ("answers_werkzeug_pe_cot.json","PE cot", 0.80),
]
print("=== M70 det-recall vs LLM-judge(werkzeug,同一批答案)===")
print(f"{'config':18}{'det-recall':>12}{'LLM-judge(报)':>16}{'judge-det':>12}")
for f,lab,j in ROWS:
    d=detrecall(f)
    if d is not None:
        print(f"{lab:18}{d:>12.3f}{j:>16.2f}{j-d:>12.3f}")
print("\n机理对照(已有实验):")
print("  ① 大结构杠杆(RAG):det 0.159→0.747(Δ+0.588) vs judge 0.19→0.94(Δ+0.75)——方向都巨大;judge 绝对宽松 ~0.2(给部分分)")
print("  ② 完整性改善(补全 M64):det +0.047 vs judge +0.01——det 对'补回漏列'敏感,judge 因部分分已给、不敏感")
print("\n诚实结论:两指标测不同东西——det=结构召回(客观但窄)、judge=综合质量(全面但主观+宽松~0.2)。各有盲区,互补非取代。")
