"""E10:敏感性检查 —— 验证消融结论不是建立在少数用例或简单用例上。

41 条用例是小样本,排名可能被几条题"绑架"。三个压力测试:
1. 剔除"全对题"(所有配置都满分 —— 它们只抬高均分,不产生区分度)
2. 再剔除"全错题"(所有配置都 0 —— 同理,只拉低均分)
3. 只看 P0 子集(核心能力题)
在每个子集上重新计算配置排名,如果冠军和关键序关系(冠军 > 单项 > baseline >
退化配置)不变,结论就是稳的;变了就要在文档里降级表述。

用法:python scripts/sensitivity.py   (结果落 results/sensitivity.md)
"""

import json

from _common import PROJECT_ROOT

CONFIGS = [
    "baseline", "chunk_function", "small_chunks", "top_k_1", "prompt_fewshot_cot",
    "graph_cards", "semantic", "hybrid", "best_stack", "best_stack_norerank",
    "best_stack_semrerank",
    # 第四阶段
    "best_stack_constcards", "best_stack_xrerank", "best_stack_final",
]


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def main():
    data = {}
    for name in CONFIGS:
        path = PROJECT_ROOT / "results" / f"{name}.json"
        if not path.exists():  # 还没跑的配置跳过,脚本在任何阶段都能用
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        data[name] = {c["id"]: c for c in d["cases"]}

    names = list(data)
    case_ids = list(next(iter(data.values())).keys())
    # 全对题/全错题判定要跨"全部配置"看
    all_perfect = [cid for cid in case_ids if all(data[n][cid]["answer_score"] >= 1.0 for n in names)]
    all_zero = [cid for cid in case_ids if all(data[n][cid]["answer_score"] <= 0.0 for n in names)]
    p0 = [cid for cid in case_ids if data[names[0]][cid]["priority"] == "P0"]

    subsets = {
        f"全集({len(case_ids)} 条)": case_ids,
        f"剔除全对题(剩 {len(case_ids) - len(all_perfect)} 条)": [c for c in case_ids if c not in all_perfect],
        f"再剔除全错题(剩 {len(case_ids) - len(all_perfect) - len(all_zero)} 条)": [
            c for c in case_ids if c not in all_perfect and c not in all_zero
        ],
        f"仅 P0({len(p0)} 条)": p0,
    }

    lines = ["# E10:敏感性检查", "",
             f"全对题(无区分度):{all_perfect}",
             f"全错题(无区分度):{all_zero}", ""]
    for title, subset in subsets.items():
        ranked = sorted(
            ((name, mean([data[name][cid]["answer_score"] for cid in subset])) for name in names),
            key=lambda x: x[1], reverse=True,
        )
        lines += [f"## {title}", "", "| 排名 | 配置 | 答案分 |", "|---|---|---|"]
        for i, (name, score) in enumerate(ranked, 1):
            lines.append(f"| {i} | {name} | {score:.3f} |")
        lines.append("")
        print(f"{title}: 第一名 {ranked[0][0]} ({ranked[0][1]:.3f}),baseline 排第 "
              f"{[n for n, _ in ranked].index('baseline') + 1}")

    out = PROJECT_ROOT / "results" / "sensitivity.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n汇总: {out}")


if __name__ == "__main__":
    main()
