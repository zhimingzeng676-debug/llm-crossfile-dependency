"""M9:把某配置打包成"自洽评测包"——每条含 生成prompt + 问题 + 标准要点 + notes。
供远端 gen_multi.py 一次性跑 N 轮生成 + 逐答打分(都在远端并发),只回传分数。

用法:python scripts/build_bundle.py <config_name> [dataset]
  读 results/prompts_<name>.json + 数据集,写 results/bundle_<name>.json
"""

import json
import sys

from _common import PROJECT_ROOT
from repomind_lab.evalkit.testcase import load_testcases


def gold_points(judge: dict) -> str:
    if judge.get("type") == "all_groups":
        return "; ".join("(" + " 或 ".join(g) + ")" for g in judge.get("groups", []))
    return ", ".join(judge.get("keywords", []))


def main():
    name = sys.argv[1]
    dataset = sys.argv[2] if len(sys.argv) > 2 else "data/testcases_werkzeug.jsonl"
    R = PROJECT_ROOT / "results"
    prompts = json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))
    cases = {c.id: c for c in load_testcases(PROJECT_ROOT / dataset)}

    bundle = []
    for p in prompts:
        cid = p["id"]
        bundle.append({
            "id": cid,
            "difficulty": p.get("difficulty", "?"),
            "category": p.get("category", "?"),
            "gen_prompt": p["prompt"],
            "question": p["question"],
            "gold": gold_points(p["judge"]),
            "notes": cases[cid].notes if cid in cases else "(无)",
        })
    out = R / f"bundle_{name}.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name}: {len(bundle)} 条 -> {out}")


if __name__ == "__main__":
    main()
