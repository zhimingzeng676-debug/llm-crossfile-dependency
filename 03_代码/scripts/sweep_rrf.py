"""E8:RRF 融合权重扫参 —— 修复"等权融合稀释强信号"的负结果。

背景(EXPERIMENTS E3):hybrid 等权融合时,BM25 路的"平庸共识"把向量路
排第一的正确块(CC-01 的 gateway.py)挤出 top3,检索命中率升了、关键用例挂了。
假设:**调低 BM25 权重**(向量为主、词法为辅)能保住向量路强信号,
同时保留 BM25 对精确标识符的补益。

做法:两组第一段配置 × 6 档权重,共 12 次评测。索引不随权重变,复用同一份。
- A 组:hybrid.yaml(哈希向量 + BM25)—— 复现 E3 场景
- B 组:best_stack_norerank.yaml(语义向量 + BM25)—— 当前冠军,看还能不能涨
盯两个数:总体(答案分/检索命中)+ 金丝雀用例 CC-01 的答案分。

用法:python scripts/sweep_rrf.py   (结果落 results/rrf_sweep.md)
"""

from _common import PROJECT_ROOT

from repomind_lab.config import ExperimentConfig
from repomind_lab.evalkit.runner import run_eval
from repomind_lab.evalkit.testcase import load_testcases

# (vector_weight, bm25_weight)。(1,0) 是"纯向量"对照,验证扫参两端的锚点。
WEIGHT_GRID = [(1.0, 1.0), (1.0, 0.5), (1.0, 0.25), (0.5, 1.0), (1.0, 0.0)]

BASE_CONFIGS = ["configs/hybrid.yaml", "configs/best_stack_norerank.yaml"]
CANARY = "CC-01"  # E3 里被等权融合搞挂的用例


def main():
    cases = load_testcases(PROJECT_ROOT / "data" / "testcases.jsonl")
    lines = ["# E8:RRF 权重扫参结果", "",
             f"金丝雀用例:{CANARY}(E3 中被等权融合稀释致 0 分)", ""]

    for base in BASE_CONFIGS:
        base_cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / base)
        lines += [f"## 第一段:{base_cfg.name}", "",
                  "| vector_w | bm25_w | 答案分 | 检索命中 | CC-01 |",
                  "|---|---|---|---|---|"]
        for wv, wb in WEIGHT_GRID:
            cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / base)
            cfg.backend.vector_weight = wv
            cfg.backend.bm25_weight = wb
            # 名字带上权重,结果 JSON 互不覆盖;索引沿用 base 的(权重不影响索引)
            cfg.name = f"{base_cfg.name}_wv{wv}_wb{wb}"
            cfg.index_dir = base_cfg.index_dir
            result = run_eval(cfg, cases, project_root=PROJECT_ROOT)
            o = result["summary"]["overall"]
            canary = next(c["answer_score"] for c in result["cases"] if c["id"] == CANARY)
            print(f"{cfg.name}: 答案 {o['avg_answer_score']:.2f} 检索 {o['retrieval_hit_rate']:.2f} {CANARY} {canary:.2f}")
            lines.append(f"| {wv} | {wb} | {o['avg_answer_score']:.2f} | {o['retrieval_hit_rate']:.2f} | {canary:.2f} |")
        lines.append("")

    out = PROJECT_ROOT / "results" / "rrf_sweep.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n汇总: {out}")


if __name__ == "__main__":
    main()
