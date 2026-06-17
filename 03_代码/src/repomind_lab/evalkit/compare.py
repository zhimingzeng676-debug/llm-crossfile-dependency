"""消融对比:把多个配置的评测结果并排成 Markdown 报告。

消融实验(ablation)的读法:所有配置都以 baseline 为参照、只改一个变量,
所以表格里任何分数差异都可以**归因到那个被改的变量**上。

报告包含三层,从粗到细:
1. 总览表:每个配置一行,总体答案分 + 检索命中率
2. 分方向表:按 category(调用链/历史/跨文件/语义)拆开 —— 一个配置经常是
   "此消彼长"(小块对精确查找好、对长上下文问题差),只看总分会掩盖这点
3. 逐用例矩阵:每条用例 × 每个配置的得分,直接看到"哪条用例被哪个配置救活/搞砸"
"""

from __future__ import annotations

import json
from pathlib import Path


def load_result(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def build_report(results: list[dict]) -> str:
    """输入若干 run_eval 的结果 dict,输出 Markdown 文本。"""
    names = [r["config_name"] for r in results]
    lines: list[str] = ["# 消融实验对比报告", ""]
    lines.append(f"参与对比的配置:{', '.join(names)}(各自只与 baseline 差一个变量)")
    lines.append("")

    # ---- 1. 总览表 ----
    lines.append("## 总览")
    lines.append("")
    lines.append("| 配置 | 平均答案分 | 检索命中率 | 用例数 | 耗时(s) |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        o = r["summary"]["overall"]
        lines.append(
            f"| {r['config_name']} | {_fmt(o['avg_answer_score'])} | "
            f"{_fmt(o['retrieval_hit_rate'])} | {o['n']} | {r['elapsed_sec']} |"
        )
    lines.append("")

    # ---- 2. 分方向表(两个指标各一张)----
    categories = sorted({cat for r in results for cat in r["summary"]["by_category"]})
    for metric, title in [("avg_answer_score", "答案分"), ("retrieval_hit_rate", "检索命中率")]:
        lines.append(f"## 分方向:{title}")
        lines.append("")
        lines.append("| 配置 | " + " | ".join(categories) + " |")
        lines.append("|---|" + "---|" * len(categories))
        for r in results:
            cells = [_fmt(r["summary"]["by_category"].get(c, {}).get(metric, 0.0)) for c in categories]
            lines.append(f"| {r['config_name']} | " + " | ".join(cells) + " |")
        lines.append("")

    # ---- 3. 逐用例答案分矩阵 ----
    lines.append("## 逐用例答案分")
    lines.append("")
    lines.append("(行 = 用例,列 = 配置;0 分说明该配置下这条用例完全失败,值得点开结果 JSON 看原因)")
    lines.append("")
    case_ids = [c["id"] for c in results[0]["cases"]]
    lines.append("| 用例 | 方向 | " + " | ".join(names) + " |")
    lines.append("|---|---|" + "---|" * len(names))
    score_map = {r["config_name"]: {c["id"]: c["answer_score"] for c in r["cases"]} for r in results}
    cat_map = {c["id"]: c["category"] for c in results[0]["cases"]}
    for cid in case_ids:
        cells = [_fmt(score_map[n].get(cid, 0.0)) for n in names]
        lines.append(f"| {cid} | {cat_map[cid]} | " + " | ".join(cells) + " |")
    lines.append("")

    return "\n".join(lines)
