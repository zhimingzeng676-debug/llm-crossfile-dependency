"""为 MockLLM 的结果(results/<name>.json,含 answer)构建裁判 prompt,用 LLM-judge 复核。
验证 M3 caveat:MockLLM 高分是不是 keyword 判定被'逐字倒卡片'骗了。

用法:python scripts/judge_mock.py <results_name>   # 如 werkzeug_full(mock 全栈)
  写 results/judgeprompts_<name>_mock.json + prompts_<name>_mock.json(供 parse 复用)
"""

import json
import sys

from _common import PROJECT_ROOT
from repomind_lab.evalkit.testcase import load_testcases
from make_judge_prompts import JUDGE_TMPL, gold_points


def main():
    name = sys.argv[1]
    R = PROJECT_ROOT / "results"
    res = json.load(open(R / f"{name}.json", encoding="utf-8"))
    cases = {c.id: c for c in load_testcases(PROJECT_ROOT / "data" / "testcases_werkzeug.jsonl")}

    judge_prompts, meta = [], []
    for c in res["cases"]:
        cid = c["id"]
        gc = cases[cid]
        jp = JUDGE_TMPL.format(
            question=c["question"],
            gold=gold_points(gc.judge.model_dump()),
            notes=gc.notes,
            answer=c["answer"],
        )
        judge_prompts.append({"id": cid, "prompt": jp})
        meta.append({"id": cid, "category": c["category"], "difficulty": c.get("difficulty", "medium")})

    tag = f"{name}_mock"
    (R / f"judgeprompts_{tag}.json").write_text(json.dumps(judge_prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / f"prompts_{tag}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{tag}: {len(judge_prompts)} 条 -> judgeprompts_{tag}.json")


if __name__ == "__main__":
    main()
