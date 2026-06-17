"""M36-37 任务一:judge-independent 确定性复算核心结论。
对每条 werkzeug 用例,用确定性字符串匹配(零 LLM)统计模型答案是否命中 gold 依赖关键词,
对比 baseline(无卡片) vs full(RAG卡片),配对 t 检验。完全不经任何裁判模型。

防同源:gold 真值同时用两套独立来源核对——
  (a) 用例自带 gold keyword(由 tree-sitter 依赖图导出);
  (b) 独立 stdlib ast 抽取(results/ast_edges_werkzeug.json,零 tree-sitter)。
报告 (a)/(b) 一致率作为"判分无关真值与 RAG 卡片解耦"的证据。
"""
import json, re, sys
from pathlib import Path
from scipy.stats import ttest_rel
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
R = ROOT/"results"; D = ROOT/"data"
OUT = R/"judge_independent"; OUT.mkdir(parents=True, exist_ok=True)

cases = [json.loads(l) for l in open(D/"testcases_werkzeug.jsonl", encoding="utf-8")
         if l.strip() and not l.startswith("//")]
ast_gold = json.load(open(R/"ast_edges_werkzeug.json", encoding="utf-8"))

def token_present(tok, text):
    """确定性:tok 作为模块/路径 token 是否出现在答案中(零 LLM)。
    允许周围有 .py / 反引号 / 斜杠 / 点;两侧不得紧邻其它单词字符以防 http∈https。"""
    t = re.escape(tok)
    return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None

def recall(ans_text, keywords):
    if not keywords: return None
    hit = sum(1 for k in keywords if token_present(k, ans_text))
    return hit/len(keywords)

def all_present(ans_text, keywords):
    """复刻原 keyword_all 判据的确定性版:全部 gold 命中=1 否则 0。"""
    if not keywords: return None
    return 1.0 if all(token_present(k, ans_text) for k in keywords) else 0.0

# ---- 独立 ast 真值:对 ast 可覆盖的类别重导 gold,与用例 gold 核对(解耦证据) ----
fwd = ast_gold["forward"]; rev = ast_gold["reverse"]
def ast_keywords_for(case):
    cat = case["category"]; src = (case.get("expected_sources") or [None])[0]
    if not src: return None
    if cat == "forward_dep":
        return {Path(x).stem for x in fwd.get(src, [])}
    if cat == "reverse_dep":
        return {Path(x).stem for x in rev.get(src, [])}
    if cat == "indirect_dep":  # 2-hop 传递闭包(独立 ast)
        one = set(fwd.get(src, []))
        two = set()
        for m in one:
            two |= set(fwd.get(m, []))
        return {Path(x).stem for x in (one | two)}
    return None  # inheritance/symbol/dataflow: ast 部分可覆盖,此处不强行重导

# 解耦核对:用例 gold ∩ 独立 ast gold
ast_cov = [c for c in cases if ast_keywords_for(c) is not None]
agree_hit = agree_tot = 0
decouple_rows = []
for c in ast_cov:
    g = set(c["judge"]["keywords"]); a = ast_keywords_for(c)
    hit = len(g & a); agree_hit += hit; agree_tot += len(g)
    decouple_rows.append({"id": c["id"], "cat": c["category"],
                          "gold": sorted(g), "ast": sorted(a), "match": f"{hit}/{len(g)}"})
decouple_rate = agree_hit/agree_tot if agree_tot else 0

# ---- 判分无关复算:baseline vs RAG ----
def load_ans(fn):
    return {x["id"]: x["answer"] for x in json.load(open(R/fn, encoding="utf-8"))}

PAIRS = {
    "baseline_vs_RAGfull": ("answers_werkzeug_baseline_qwen.json", "answers_werkzeug_full_qwen.json"),
    "purellm_vs_graphcards": ("answers_werkzeug_purellm_qwen.json", "answers_werkzeug_graphcards_qwen.json"),
}
report = {"decouple_rate": decouple_rate, "decouple_n_tokens": agree_tot, "pairs": {}}
for name, (fb, ff) in PAIRS.items():
    ab, af = load_ans(fb), load_ans(ff)
    rec_b, rec_f, all_b, all_f, rows = [], [], [], [], []
    for c in cases:
        cid = c["id"]; kw = c["judge"]["keywords"]
        if cid not in ab or cid not in af: continue
        rb, rf = recall(ab[cid], kw), recall(af[cid], kw)
        sb, sf = all_present(ab[cid], kw), all_present(af[cid], kw)
        rec_b.append(rb); rec_f.append(rf); all_b.append(sb); all_f.append(sf)
        rows.append({"id": cid, "cat": c["category"], "recall_base": round(rb,3),
                     "recall_rag": round(rf,3), "allkw_base": sb, "allkw_rag": sf})
    n = len(rec_b)
    mb, mf = sum(rec_b)/n, sum(rec_f)/n
    ab_, af_ = sum(all_b)/n, sum(all_f)/n
    t, p = ttest_rel(rec_f, rec_b)
    report["pairs"][name] = {
        "n": n, "det_recall_baseline": round(mb,4), "det_recall_rag": round(mf,4),
        "det_recall_delta": round(mf-mb,4), "ttest_t": round(float(t),3), "ttest_p": float(p),
        "allkw_acc_baseline": round(ab_,4), "allkw_acc_rag": round(af_,4),
        "allkw_acc_delta": round(af_-ab_,4),
    }
    json.dump({"summary": report["pairs"][name], "rows": rows},
              open(OUT/f"recompute_{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

json.dump({"decouple_rate": decouple_rate, "decouple_n_tokens": agree_tot, "rows": decouple_rows},
          open(OUT/"decouple_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(report, open(OUT/"recompute_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("=== 判分无关复算(零 LLM,确定性字符串匹配) ===")
print(f"解耦核对:用例 gold vs 独立 ast gold 一致 {agree_hit}/{agree_tot} = {decouple_rate:.1%}"
      f"(ast 可覆盖 {len(ast_cov)} 例)")
for name, s in report["pairs"].items():
    print(f"\n[{name}] n={s['n']}")
    print(f"  确定性 gold-recall:  baseline {s['det_recall_baseline']:.3f}  ->  RAG {s['det_recall_rag']:.3f}"
          f"  (delta +{s['det_recall_delta']:.3f}, paired t={s['ttest_t']}, p={s['ttest_p']:.2e})")
    print(f"  确定性 keyword_all:  baseline {s['allkw_acc_baseline']:.3f}  ->  RAG {s['allkw_acc_rag']:.3f}"
          f"  (delta +{s['allkw_acc_delta']:.3f})")
print("\n写出:", OUT)
