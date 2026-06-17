"""M17:两独立裁判家族(Coder vs internLM)的评分者间一致性(IRR)——回应评委"无IRR"。
对全部 7 条件×56 题的逐题分数算 Pearson/Spearman + 二值化(0.5阈)Cohen's kappa。
"""
import json, sys
from pathlib import Path
from scipy import stats
sys.stdout.reconfigure(encoding="utf-8")
P = Path(__file__).resolve().parent.parent / "results" / "phaseA"
CONDS = ["baseline_general","purellm_general","graphcards_general","full_general","pe_system","pe_cot","pe_domain"]

def load(cond, tag):
    d = json.load(open(P / f"scores_{cond}_{tag}.json", encoding="utf-8"))
    return {c["id"]: c["score"] for c in d["runs"][0]}

pairs = {}
for tag in ("qwenjudge","coderjudge","internjudge"):
    v = []
    for cond in CONDS:
        s = load(cond, tag)
        for i in sorted(s): v.append(s[i])
    pairs[tag] = v

def kappa(a, b, thr=0.5):
    A = [1 if x>=thr else 0 for x in a]; B = [1 if x>=thr else 0 for x in b]
    n = len(A); po = sum(1 for x,y in zip(A,B) if x==y)/n
    pa1 = sum(A)/n; pb1 = sum(B)/n
    pe = pa1*pb1 + (1-pa1)*(1-pb1)
    return (po-pe)/(1-pe) if pe<1 else 1.0, po

def report(t1, t2):
    a, b = pairs[t1], pairs[t2]
    r,_ = stats.pearsonr(a,b); rho,_ = stats.spearmanr(a,b); k,po = kappa(a,b)
    print(f"  {t1:11s} vs {t2:11s}: Pearson r={r:.3f}  Spearman ρ={rho:.3f}  二值κ={k:.3f}(一致率{po:.2%}), N={len(a)}")

print("两独立家族裁判 IRR(回应'无IRR',N=7条件×56题=392 逐题判分):")
report("coderjudge","internjudge")
print("\n参考(含 self):")
report("qwenjudge","coderjudge")
report("qwenjudge","internjudge")
