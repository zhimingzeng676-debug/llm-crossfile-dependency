"""解析裁判输出(judgeanswers_<name>.json)→ LLM-judge 分,产出汇总。

用法:python scripts/parse_judge.py <name>
  读 results/prompts_<name>.json(取 category/difficulty)+ results/judgeanswers_<name>.json,
  写 results/llmjudge_<name>.json,打印总体/分难度/分方向 LLM-judge 分。
"""

import json
import re
import sys

from _common import PROJECT_ROOT


def parse_score(txt):
    m = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', txt)
    if m:
        return max(0.0, min(1.0, float(m.group(1))))
    return None


def main():
    name = sys.argv[1]
    R = PROJECT_ROOT / "results"
    meta = {p["id"]: p for p in json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))}
    judged = {a["id"]: a["answer"] for a in json.load(open(R / f"judgeanswers_{name}.json", encoding="utf-8"))}

    rows = []
    parse_fail = 0
    for cid, p in meta.items():
        s = parse_score(judged.get(cid, ""))
        if s is None:
            parse_fail += 1
            s = 0.0  # 解析失败按 0(保守);记数
        rows.append({"id": cid, "category": p["category"], "difficulty": p["difficulty"], "llm_score": s})

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    overall = mean([r["llm_score"] for r in rows])
    by_diff = {d: mean([r["llm_score"] for r in rows if r["difficulty"] == d])
               for d in ("easy", "medium", "hard")}
    by_cat = {c: mean([r["llm_score"] for r in rows if r["category"] == c])
              for c in sorted({r["category"] for r in rows})}

    out = {"config_name": name, "n": len(rows), "parse_fail": parse_fail,
           "overall": overall, "by_difficulty": by_diff, "by_category": by_cat, "cases": rows}
    (R / f"llmjudge_{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{name}] LLM-judge 总体 {overall:.2f}  (解析失败 {parse_fail})  "
          f"难度 {dict((d, round(v,2)) for d,v in by_diff.items())}")


if __name__ == "__main__":
    main()
