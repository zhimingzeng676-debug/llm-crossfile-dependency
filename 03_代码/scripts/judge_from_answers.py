"""把 prompts + 远端生成的 answers 合并判定,产出 run_eval 同格式的结果 JSON。

用法:python scripts/judge_from_answers.py <config_name>
  读 results/prompts_<name>.json + results/answers_<name>.json,
  写 results/<name>.json(可被对比/误差分析工具直接复用)。
"""

import json
import sys

from _common import PROJECT_ROOT

from repomind_lab.evalkit.judges import judge_answer, judge_retrieval, retrieval_metrics
from repomind_lab.evalkit.runner import _aggregate
from repomind_lab.evalkit.testcase import JudgeSpec


def main():
    name = sys.argv[1]
    R = PROJECT_ROOT / "results"
    prompts = json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))
    answers = {a["id"]: a["answer"] for a in json.load(open(R / f"answers_{name}.json", encoding="utf-8"))}

    case_results = []
    for p in prompts:
        ans = answers.get(p["id"], "(缺失)")
        aj = judge_answer(ans, JudgeSpec(**p["judge"]))
        rsrc = p["retrieved_sources"]
        rj = judge_retrieval(rsrc, p["expected_sources"])
        m = retrieval_metrics(rsrc, p["expected_sources"])
        case_results.append({
            "id": p["id"], "category": p["category"], "priority": p.get("priority", "P1"),
            "difficulty": p["difficulty"], "question": p["question"],
            "answer": ans, "answer_score": round(aj.score, 4), "answer_judge_detail": aj.detail,
            "retrieval_hit": rj.score, "retrieval_detail": rj.detail,
            "recall_at_k": m["recall"], "mrr": m["mrr"],
            "retrieved": [{"chunk_id": s, "score": 0.0} for s in rsrc],
        })

    summary = _aggregate(case_results)
    out = {"config_name": name, "n_cases": len(case_results), "summary": summary, "cases": case_results}
    (R / f"{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    o = summary["overall"]
    print(f"[{name}] 答案分 {o['avg_answer_score']:.2f}  Recall@K {o['recall_at_k']:.2f}  MRR {o['mrr']:.2f}")
    bd = summary.get("by_difficulty", {})
    print("  按难度:", {d: round(bd[d]["avg_answer_score"], 2) for d in ("easy", "medium", "hard") if d in bd})
    print("  按方向:", {c: round(v["avg_answer_score"], 2) for c, v in summary["by_category"].items()})


if __name__ == "__main__":
    main()
