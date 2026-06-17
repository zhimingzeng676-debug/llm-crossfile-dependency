"""M42 打分:记忆 vs 结构。judge-independent 关键词召回(零 LLM)。
2×2:{seen,unseen}×{baseline,full}。seen 用真名 gold,unseen 用改名 gold(各自对应)。
关键分解:
  - 切分有效性:unseen_baseline 应 << seen_baseline(改名让记忆失效)。
  - 纯结构增益(无记忆):unseen_full − unseen_baseline。
  - 记忆独立威力:seen_baseline − unseen_baseline。
  - 卡片性能是否迁移:unseen_full vs seen_full。
  - RAG 增益对比:gain_seen vs gain_unseen。
披露:full 卡片按设计就含 gold 依赖(依赖卡片本就是把结构喂进上下文=RAG 机制),
  这不是隐藏循环;baseline(无卡片)对照已隔离"纯记忆";seen/unseen 隔离"是否背过"。
全样本 + 分类别(forward/reverse)多口径全列(M41 教训:不挑子集)。
"""
import json, re, sys
from pathlib import Path
from scipy.stats import ttest_rel
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
M = ROOT/"results"/"memstruct"
gm = json.load(open(M/"goldmap.json", encoding="utf-8"))

def present(tok, text):
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', tok):
        t = re.escape(tok); return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None
    return tok.lower() in text.lower()
def recall(text, gold):
    return sum(1 for k in gold if present(k, text))/len(gold) if gold else None

def gold_for(cid, group):
    return gm[cid][f"{group}_gold"]

def load(cond):
    fp = M/f"ans_{cond}.json"
    if not fp.exists(): return None
    group = "seen" if cond.startswith("seen") else "unseen"
    per = {}
    for run in json.load(open(fp, encoding="utf-8"))["runs"]:
        for x in run:
            g = gold_for(x["id"], group)
            per.setdefault(x["id"], []).append(recall(x["answer"], g))
    return {i: sum(v)/len(v) for i, v in per.items()}

CONDS = ["seen_baseline", "seen_full", "unseen_baseline", "unseen_full",
         "seen_baseline_forced", "unseen_baseline_forced"]
S = {c: load(c) for c in CONDS}
S = {k: v for k, v in S.items() if v is not None}
if "seen_full" not in S:
    print("答案未就绪。"); sys.exit(0)
HAS_FORCED = "seen_baseline_forced" in S and "unseen_baseline_forced" in S
ids = list(gm)
kinds = {i: gm[i]["kind"] for i in ids}

def mean(d, sub): return sum(d[i] for i in sub)/len(sub)
def block(sub, label):
    sb, sf = mean(S["seen_baseline"], sub), mean(S["seen_full"], sub)
    ub, uf = mean(S["unseen_baseline"], sub), mean(S["unseen_full"], sub)
    return {"label": label, "n": len(sub),
            "seen_baseline": round(sb,3), "seen_full": round(sf,3), "gain_seen": round(sf-sb,3),
            "unseen_baseline": round(ub,3), "unseen_full": round(uf,3), "gain_unseen": round(uf-ub,3),
            "memory_standalone(seenB-unseenB)": round(sb-ub,3),
            "structure_no_memory(unseenF-unseenB)": round(uf-ub,3),
            "card_transfer(unseenF-seenF)": round(uf-sf,3)}

report = {"all": block(ids, "全样本"),
          "forward": block([i for i in ids if kinds[i]=="forward"], "forward"),
          "reverse": block([i for i in ids if kinds[i]=="reverse"], "reverse")}

def paired(a, b):
    va=[S[a][i] for i in ids]; vb=[S[b][i] for i in ids]; t,p=ttest_rel(va,vb)
    return {"a":round(sum(va)/len(va),3),"b":round(sum(vb)/len(vb),3),"delta":round((sum(va)-sum(vb))/len(va),3),"t":round(float(t),2),"p":float(p)}
report["stats"] = {
    "structure_no_memory_unseenF_vs_unseenB": paired("unseen_full","unseen_baseline"),
    "card_transfer_unseenF_vs_seenF": paired("unseen_full","seen_full")}
if HAS_FORCED:
    sbf = mean(S["seen_baseline_forced"], ids); ubf = mean(S["unseen_baseline_forced"], ids)
    report["forced_baseline"] = {
        "seen_baseline_forced": round(sbf,3), "unseen_baseline_forced": round(ubf,3),
        "pure_memory_contribution(seenF-unseenF)": round(sbf-ubf,3),
        "note": "强制猜测(禁abstain)下的纯记忆贡献:seen 减 unseen"}
    report["stats"]["memory_seenForced_vs_unseenForced"] = paired("seen_baseline_forced","unseen_baseline_forced")
json.dump(report, open(M/"score_report.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)

print("=== M42 记忆 vs 结构(judge-independent 关键词召回,全样本多口径)===")
for key in ["all","forward","reverse"]:
    r=report[key]
    print(f"\n[{r['label']} n={r['n']}]")
    print(f"  seen :  baseline {r['seen_baseline']:.3f}  full {r['seen_full']:.3f}   gain +{r['gain_seen']:.3f}")
    print(f"  unseen: baseline {r['unseen_baseline']:.3f}  full {r['unseen_full']:.3f}   gain +{r['gain_unseen']:.3f}")
    print(f"  记忆独立威力(seenB-unseenB)={r['memory_standalone(seenB-unseenB)']:+.3f}  "
          f"纯结构增益(unseenF-unseenB)={r['structure_no_memory(unseenF-unseenB)']:+.3f}  "
          f"卡片迁移(unseenF-seenF)={r['card_transfer(unseenF-seenF)']:+.3f}")
if HAS_FORCED:
    fb=report["forced_baseline"]
    print(f"\n[强制猜测 baseline(去 abstain 混淆)全样本]")
    print(f"  seen_forced {fb['seen_baseline_forced']:.3f}  unseen_forced {fb['unseen_baseline_forced']:.3f}  "
          f"纯记忆贡献(seen-unseen)={fb['pure_memory_contribution(seenF-unseenF)']:+.3f}")
print("\n[配对统计 全样本]")
for k,v in report["stats"].items():
    print(f"  {k}: {v['b']}->{v['a']} (Δ{v['delta']:+}, t={v['t']}, p={v['p']:.2e})")
print("\n写出", M/"score_report.json")
