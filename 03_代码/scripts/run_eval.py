"""跑一个配置的完整评测,终端打印汇总表,完整结果落盘 results/<配置名>.json。

用法:
    python scripts/run_eval.py                                   # 默认 mock baseline
    python scripts/run_eval.py configs/small_chunks.yaml
    python scripts/run_eval.py configs/werkzeug_baseline.yaml data/testcases_werkzeug.jsonl
"""

import sys

from _common import PROJECT_ROOT

from repomind_lab.config import ExperimentConfig
from repomind_lab.evalkit.runner import run_eval
from repomind_lab.evalkit.testcase import load_testcases

from rich.console import Console
from rich.table import Table


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "configs/baseline.yaml"
    cases_path = sys.argv[2] if len(sys.argv) > 2 else "data/testcases.jsonl"
    cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / config_path)
    cases = load_testcases(PROJECT_ROOT / cases_path)

    result = run_eval(cfg, cases, project_root=PROJECT_ROOT)

    console = Console()
    o = result["summary"]["overall"]
    console.print(f"\n[bold]配置 {cfg.name}[/bold]:{result['n_cases']} 条用例,耗时 {result['elapsed_sec']}s")
    console.print(
        f"总体:答案分 [bold]{o['avg_answer_score']:.2f}[/bold]  "
        f"检索命中率 {o['retrieval_hit_rate']:.2f}  "
        f"Recall@K [bold]{o['recall_at_k']:.2f}[/bold]  MRR [bold]{o['mrr']:.2f}[/bold]\n"
    )

    table = Table(title="分方向结果")
    table.add_column("方向")
    table.add_column("用例数", justify="right")
    table.add_column("答案分", justify="right")
    table.add_column("Recall@K", justify="right")
    table.add_column("MRR", justify="right")
    for cat, s in result["summary"]["by_category"].items():
        table.add_row(cat, str(s["n"]), f"{s['avg_answer_score']:.2f}",
                      f"{s['recall_at_k']:.2f}", f"{s['mrr']:.2f}")
    console.print(table)

    if result["summary"].get("by_difficulty"):
        dt = Table(title="分难度结果")
        dt.add_column("难度"); dt.add_column("用例数", justify="right")
        dt.add_column("答案分", justify="right"); dt.add_column("Recall@K", justify="right")
        for diff, s in result["summary"]["by_difficulty"].items():
            dt.add_row(diff, str(s["n"]), f"{s['avg_answer_score']:.2f}", f"{s['recall_at_k']:.2f}")
        console.print(dt)

    # 低分用例单独点名,方便直接去结果 JSON 里查原因
    weak = [c for c in result["cases"] if c["answer_score"] < 0.5]
    if weak:
        console.print("\n[yellow]答案分 < 0.5 的用例(去结果 JSON 里看 answer 和判定依据):[/yellow]")
        for c in weak:
            console.print(f"  {c['id']} [{c['category']}] {c['answer_score']:.2f}  {c['question']}")
    console.print(f"\n完整结果: {result['out_path']}")


if __name__ == "__main__":
    main()
