"""消融实验:同一套用例 × 多个配置,自动跑完并生成 Markdown 对比报告。

用法:
    python scripts/run_ablation.py                                    # 跑默认的 5 个配置
    python scripts/run_ablation.py configs/baseline.yaml configs/top_k_1.yaml   # 指定配置

输出:
    results/<每个配置>.json   + results/ablation_report.md
"""

import sys

from _common import PROJECT_ROOT

from repomind_lab.config import ExperimentConfig
from repomind_lab.evalkit.compare import build_report
from repomind_lab.evalkit.runner import run_eval
from repomind_lab.evalkit.testcase import load_testcases

# 默认对比组:baseline + 每次只改一个变量的变体(第二阶段加入 graph_cards /
# semantic / hybrid),最后的 best_stack 是"全部叠满"的组合验证(非严格消融)
DEFAULT_CONFIGS = [
    "configs/baseline.yaml",
    "configs/chunk_function.yaml",
    "configs/small_chunks.yaml",
    "configs/top_k_1.yaml",
    "configs/prompt_fewshot_cot.yaml",
    "configs/graph_cards.yaml",
    "configs/semantic.yaml",
    "configs/hybrid.yaml",
    "configs/best_stack.yaml",
    "configs/best_stack_norerank.yaml",  # 归因对照:与 best_stack 只差 rerank 开关
]


def main():
    config_paths = sys.argv[1:] or DEFAULT_CONFIGS
    cases = load_testcases(PROJECT_ROOT / "data" / "testcases.jsonl")

    results = []
    for path in config_paths:
        cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / path)
        print(f"==> 评测 {cfg.name} ...")
        result = run_eval(cfg, cases, project_root=PROJECT_ROOT)
        o = result["summary"]["overall"]
        print(f"    答案分 {o['avg_answer_score']:.2f}  检索命中率 {o['retrieval_hit_rate']:.2f}")
        results.append(result)

    report = build_report(results)
    out_path = PROJECT_ROOT / "results" / "ablation_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\n对比报告已生成: {out_path}")


if __name__ == "__main__":
    main()
