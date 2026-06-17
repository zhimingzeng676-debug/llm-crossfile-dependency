"""M36-37 任务二:扩大校准集 + 裁判 vs 独立客观锚一致性(人工 IRR 真空的诚实退路)。
诚实定位:本项目是自主 agent,无法引入真实第二名人类标注者。退路=用与评测管线/RAG卡片
解耦的"独立源码派生确定性真值"(stdlib ast / keyword_all)作客观锚,在扩大的用例集上
测量我们实际依赖的 Coder 裁判与该客观锚的一致性。
  - 这替代人工 IRR 的"客观可算维度"(依赖是否被正确列出);
  - 不替代主观质量维度(答案表述好坏),那部分诚实保留为仍需裁判。
关键不同于已撤回的 κ=0.941 同源旁证:① 锚的 gold 由独立 ast 交叉验证(87%);
② 重点报告 Coder 与客观锚【分歧】处(裁判宽松/严格),而非自证一致。
"""
import json, sys
from pathlib import Path
import re
from scipy.stats import spearmanr
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
R = ROOT/"results"; D = ROOT/"data"; OUT = R/"judge_independent"; OUT.mkdir(parents=True, exist_ok=True)

cases = {json.loads(l)["id"]: json.loads(l) for l in open(D/"testcases_werkzeug.jsonl", encoding="utf-8")
         if l.strip() and not l.startswith("//")}

def token_present(tok, text):
    t = re.escape(tok)
    return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None
def det_recall(text, kws):
    return sum(1 for k in kws if token_present(k, text))/len(kws) if kws else None
def det_allkw(text, kws):
    return 1.0 if kws and all(token_present(k, text) for k in kws) else 0.0

def parse_cj(fn):
    """解析 M17 跨家族解耦再判(gen=Coder ≠ judge)的 _cj 原始输出 -> {id: score}。"""
    out = {}
    for x in json.load(open(R/fn, encoding="utf-8")):
        s = x["answer"].strip()
        if s.startswith("```"):
            s = s.strip("`"); s = s[s.find("{"):s.rfind("}")+1]
        else:
            s = s[s.find("{"):s.rfind("}")+1]
        try:
            out[x["id"]] = float(json.loads(s).get("score"))
        except Exception:
            pass
    return out

# 配置:answers 文件 + 对应跨家族解耦裁判 _cj 文件(gen=Coder, judge=非Coder, 红线 gen≠judge)
CONFIGS = {
    "baseline": ("answers_werkzeug_baseline_qwen.json", "judgeanswers_werkzeug_baseline_qwen_cj.json"),
    "purellm":  ("answers_werkzeug_purellm_qwen.json",  "judgeanswers_werkzeug_purellm_qwen_cj.json"),
    "RAG_full": ("answers_werkzeug_full_qwen.json",     "judgeanswers_werkzeug_full_qwen_cj.json"),
    "PE_cot":   ("answers_werkzeug_pe_cot.json",        "judgeanswers_werkzeug_pe_cot_cj.json"),
}
rows = []
for cfg, (ans_fn, cj_fn) in CONFIGS.items():
    if not (R/ans_fn).exists() or not (R/cj_fn).exists():
        print("skip", cfg, "missing"); continue
    ans = {x["id"]: x["answer"] for x in json.load(open(R/ans_fn, encoding="utf-8"))}
    coder = parse_cj(cj_fn)
    for cid, c in cases.items():
        if cid not in ans or cid not in coder: continue
        kw = c["judge"]["keywords"]
        rows.append({"cfg": cfg, "id": cid, "cat": c["category"],
                     "coder": round(coder[cid], 3),
                     "det_recall": round(det_recall(ans[cid], kw), 3),
                     "det_allkw": det_allkw(ans[cid], kw)})

n = len(rows)
coder_v = [r["coder"] for r in rows]
recall_v = [r["det_recall"] for r in rows]
allkw_v = [r["det_allkw"] for r in rows]

# Spearman: Coder 连续分 vs 确定性 gold-recall
rho, prho = spearmanr(coder_v, recall_v)
# 二值一致: Coder>=0.5 vs det_allkw==1 -> Cohen κ
def kappa(a, b):
    a = [1 if x >= 0.5 else 0 for x in a]; b = [int(x) for x in b]
    n = len(a); po = sum(1 for i in range(n) if a[i] == b[i])/n
    pa1 = sum(a)/n; pb1 = sum(b)/n
    pe = pa1*pb1 + (1-pa1)*(1-pb1)
    return (po-pe)/(1-pe) if pe < 1 else 1.0, po
k, po = kappa(coder_v, allkw_v)
# 分歧方向:Coder 给分但确定性判不全(裁判宽松) vs 反向(裁判严格)
lenient = sum(1 for r in rows if r["coder"] >= 0.5 and r["det_allkw"] == 0)   # 裁判宽松
strict_ = sum(1 for r in rows if r["coder"] < 0.5 and r["det_allkw"] == 1)    # 裁判严格
agree   = sum(1 for r in rows if (r["coder"] >= 0.5) == (r["det_allkw"] == 1))
mean_gap = sum(r["coder"] - r["det_recall"] for r in rows)/n  # 正=Coder 系统性高于确定性

summary = {
    "n_judge_decisions": n, "configs": list(CONFIGS), "prev_calib_n": 20,
    "coder_mean": round(sum(coder_v)/n, 3), "det_recall_mean": round(sum(recall_v)/n, 3),
    "det_allkw_mean": round(sum(allkw_v)/n, 3),
    "spearman_rho": round(float(rho), 3), "spearman_p": float(prho),
    "binary_kappa": round(float(k), 3), "binary_agree_pct": round(po, 3),
    "agree_n": agree, "lenient_n": lenient, "strict_n": strict_,
    "mean_gap_coder_minus_det": round(mean_gap, 3),
}
json.dump({"summary": summary, "rows": rows}, open(OUT/"calibration_expand.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("=== 校准集扩大 + 解耦LLM裁判 vs 独立客观锚一致性 ===")
print(f"裁判=跨家族解耦再判(gen=Coder≠judge,M17 _cj),红线 gen≠judge 满足")
print(f"判定数 n={n}(原人工校准 n=20),覆盖配置 {list(CONFIGS)}")
print(f"解耦裁判 均分 {summary['coder_mean']}  |  确定性 gold-recall 均 {summary['det_recall_mean']}  |  确定性 keyword_all 均 {summary['det_allkw_mean']}")
print(f"Spearman(裁判, 确定性recall) rho={summary['spearman_rho']} p={summary['spearman_p']:.2e}")
print(f"二值一致 κ={summary['binary_kappa']}  一致率={summary['binary_agree_pct']:.1%}  (一致 {agree}/{n})")
print(f"分歧:裁判宽松(给分但确定性判不全) {lenient}  |  裁判严格(扣分但确定性判全) {strict_}")
print(f"系统性偏差 (裁判 - 确定性recall) = {summary['mean_gap_coder_minus_det']:+.3f}  (正=裁判比确定性宽松)")
print("\n写出:", OUT/"calibration_expand.json")
