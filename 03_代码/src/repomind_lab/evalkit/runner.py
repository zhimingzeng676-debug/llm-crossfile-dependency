"""跑分器:一个实验配置 × 一套测试用例 → 一份结果 JSON。

输出两个层面的指标:
- answer_score   回答质量(判定器打分,0~1,可有部分分)
- retrieval_hit  检索命中率(预期来源是否被检回,0/1)

为什么要两个指标:RAG 失败有两种模式 ——【检索就错了】和【检索对了
但生成没用上】。只看最终答案分无法区分二者,优化就无从下手。
两个指标一对照,归因一目了然:
    retrieval_hit=1, answer_score 低  → 问题出在 prompt/生成侧
    retrieval_hit=0                   → 问题出在切块/embedding/检索侧

结果 JSON 里保存了每条用例的完整中间产物(答案原文、检索到的块、判定依据),
这样看到一个低分时可以直接翻 JSON 定位原因,不用重跑。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..config import ExperimentConfig
from ..pipeline import RagPipeline, build_index
from .judges import judge_answer, judge_retrieval, retrieval_metrics
from .testcase import TestCase


def run_eval(
    cfg: ExperimentConfig,
    cases: list[TestCase],
    project_root: str | Path = ".",
    out_dir: str | Path = "results",
) -> dict:
    """跑一个配置的完整评测,落盘并返回结果 dict。"""
    root = Path(project_root)

    # 索引不存在就自动构建 —— 让 run_eval 成为"一条命令出结果"的入口,
    # 不要求使用者记住"先 build_index 再 run_eval"的顺序。
    # backend=none(纯 LLM 无 RAG)不需要索引,跳过构建。
    if cfg.backend.type != "none" and not (root / cfg.index_dir / "index.faiss").exists():
        stats = build_index(cfg, project_root=root)
        print(f"[{cfg.name}] 索引不存在,已自动构建({stats['n_chunks']} 块)")

    pipe = RagPipeline(cfg, project_root=root)

    case_results = []
    t0 = time.time()
    for case in cases:
        result = pipe.answer(case.question)
        ans = judge_answer(result.answer, case.judge)
        retrieved_sources = [rc.chunk.source for rc in result.retrieved]
        ret = judge_retrieval(retrieved_sources, case.expected_sources)
        metrics = retrieval_metrics(retrieved_sources, case.expected_sources)
        case_results.append(
            {
                "id": case.id,
                "category": case.category,
                "priority": case.priority,
                "difficulty": case.difficulty,
                "question": case.question,
                "answer": result.answer,
                "answer_score": round(ans.score, 4),
                "answer_judge_detail": ans.detail,
                "retrieval_hit": ret.score,  # 1.0 / 0.0 / -1.0(不适用)
                "retrieval_detail": ret.detail,
                "recall_at_k": metrics["recall"],  # Recall@K(K=top_k),None=不适用
                "mrr": metrics["mrr"],             # 第一个相关块的排名倒数
                "retrieved": [
                    {"chunk_id": rc.chunk.chunk_id, "score": round(rc.score, 4)}
                    for rc in result.retrieved
                ],
            }
        )
    elapsed = time.time() - t0

    summary = _aggregate(case_results)
    output = {
        "config_name": cfg.name,
        "config": cfg.model_dump(),
        "n_cases": len(cases),
        "elapsed_sec": round(elapsed, 2),
        "summary": summary,
        "cases": case_results,
    }

    out_path = root / out_dir / f"{cfg.name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    output["out_path"] = str(out_path)
    return output


def _aggregate(case_results: list[dict]) -> dict:
    """聚合:总体 + 按 category 分组的平均答案分与检索命中率。"""

    def mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    def stats(rows: list[dict]) -> dict:
        ret_applicable = [r["retrieval_hit"] for r in rows if r["retrieval_hit"] is not None and r["retrieval_hit"] >= 0]
        recalls = [r["recall_at_k"] for r in rows if r.get("recall_at_k") is not None]
        mrrs = [r["mrr"] for r in rows if r.get("mrr") is not None]
        return {
            "n": len(rows),
            "avg_answer_score": mean([r["answer_score"] for r in rows]),
            "retrieval_hit_rate": mean(ret_applicable),
            "recall_at_k": mean(recalls),  # 平均 Recall@K
            "mrr": mean(mrrs),             # 平均 MRR
        }

    by_category: dict[str, dict] = {}
    for cat in sorted({r["category"] for r in case_results}):
        by_category[cat] = stats([r for r in case_results if r["category"] == cat])

    # 按难度分组(M1-2 新增:难题要能拉开配置差距,分难度看才看得出)
    by_difficulty: dict[str, dict] = {}
    for diff in ["easy", "medium", "hard"]:
        rows = [r for r in case_results if r.get("difficulty") == diff]
        if rows:
            by_difficulty[diff] = stats(rows)

    return {"overall": stats(case_results), "by_category": by_category, "by_difficulty": by_difficulty}
