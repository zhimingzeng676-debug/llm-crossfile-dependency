"""为某配置生成 LLM-judge 的判定 prompt(本地组装,远端由裁判模型打分)。

裁判看:问题 + 标准答案要点(数据集 ground truth) + 模型回答,
输出 JSON {score, hit, total, reason}。语义判定:命中正确文件/符号/关系即算对,
不计措辞;多列正确信息不扣分;只有遗漏要点或矛盾才扣分。

用法:python scripts/make_judge_prompts.py <config_name>
  读 results/prompts_<name>.json + results/answers_<name>.json + 数据集 notes,
  写 results/judgeprompts_<name>.json(复用 run_remote_gen 跑)。
"""

import json
import sys

from _common import PROJECT_ROOT
from repomind_lab.evalkit.testcase import load_testcases

JUDGE_TMPL = """你是代码依赖分析评测裁判,只负责判断"模型回答"是否答对了"标准答案要点"。
评分标准(务必遵守):
- 命中正确的文件名/符号名/依赖或继承关系即算答对,**不计较措辞、语言、格式**;
- 模型多列了正确的额外信息**不扣分**;
- 只有**遗漏了要点**或给出**矛盾/错误**信息才扣分;
- 对"列出多个"的问题,按命中要点的**比例**打分(命中数/要点总数)。

[问题] {question}

[标准答案要点 — 必须命中这些] {gold}
[补充说明 — 标准答案的完整描述] {notes}

[模型回答]
{answer}

只输出一行 JSON,不要任何额外文字:
{{"hit": <命中要点数,整数>, "total": <要点总数,整数>, "score": <hit/total,0到1小数>, "reason": "<20字内理由>"}}"""


def gold_points(judge: dict) -> str:
    t = judge.get("type")
    if t == "all_groups":
        return "; ".join("(" + " 或 ".join(g) + ")" for g in judge.get("groups", []))
    return ", ".join(judge.get("keywords", []))


def main():
    name = sys.argv[1]
    dataset = sys.argv[2] if len(sys.argv) > 2 else "data/testcases_werkzeug.jsonl"
    R = PROJECT_ROOT / "results"
    prompts = json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))
    answers = {a["id"]: a["answer"] for a in json.load(open(R / f"answers_{name}.json", encoding="utf-8"))}
    # 数据集 notes(ground truth 的完整描述)
    cases = {c.id: c for c in load_testcases(PROJECT_ROOT / dataset)}

    out = []
    for p in prompts:
        cid = p["id"]
        jp = JUDGE_TMPL.format(
            question=p["question"],
            gold=gold_points(p["judge"]),
            notes=cases[cid].notes if cid in cases else "(无)",
            answer=answers.get(cid, "(缺失)"),
        )
        out.append({"id": cid, "prompt": jp})

    out_path = R / f"judgeprompts_{name}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name}: {len(out)} 条 judge-prompt -> {out_path}")


if __name__ == "__main__":
    main()
