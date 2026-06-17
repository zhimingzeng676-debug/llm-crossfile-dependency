"""生成消融实验可视化图表(答辩用),落盘 results/charts/*.png。

三张图,各回答一个问题:
1. bars.png    —— 哪个配置最好?(配置 × 双指标 分组柱状图)
2. radar.png   —— 各配置在四个方向上的形状差异?(雷达图,看"此消彼长")
3. heatmap.png —— 每条用例在每个配置下的命运?(逐用例热力图,定位失分点)

用法:python scripts/make_charts.py
"""

import json

import matplotlib

matplotlib.use("Agg")  # 无界面环境直接出图
import matplotlib.pyplot as plt
import numpy as np

from _common import PROJECT_ROOT

# Windows 中文字体;负号用 ASCII 形式避免方块
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

CONFIGS = [
    "baseline", "chunk_function", "small_chunks", "top_k_1", "prompt_fewshot_cot",
    "graph_cards", "semantic", "hybrid", "best_stack", "best_stack_norerank",
    # 第四阶段(存在对应结果 JSON 时才画,见 load_all 的过滤)
    "best_stack_constcards", "best_stack_xrerank", "best_stack_final",
]
RADAR_CONFIGS = ["baseline", "chunk_function", "graph_cards", "semantic", "best_stack_norerank"]
CATEGORIES = ["call_chain", "history", "cross_file", "semantic"]
CAT_LABELS = ["调用链", "历史追踪", "跨文件", "语义检索"]


def load_all():
    data = {}
    for name in CONFIGS:
        path = PROJECT_ROOT / "results" / f"{name}.json"
        if path.exists():  # 还没跑过的配置直接跳过,脚本在任何阶段都能用
            data[name] = json.loads(path.read_text(encoding="utf-8"))
    return data


def chart_bars(data, out_dir):
    names = list(data)
    n = len(names)
    ans = [data[n]["summary"]["overall"]["avg_answer_score"] for n in names]
    ret = [data[n]["summary"]["overall"]["retrieval_hit_rate"] for n in names]
    x = np.arange(n)
    fig, ax = plt.subplots(figsize=(max(12, 1.2 * n), 5.5))
    b1 = ax.bar(x - 0.2, ans, 0.38, label="答案分", color="#4C72B0")
    b2 = ax.bar(x + 0.2, ret, 0.38, label="检索命中率", color="#DD8452")
    ax.bar_label(b1, fmt="%.2f", fontsize=8)
    ax.bar_label(b2, fmt="%.2f", fontsize=8)
    ax.set_xticks(x, names, rotation=25, ha="right", fontsize=9)
    ax.set_ylim(0, 1.08)
    ax.set_title(f"消融实验总览:{n} 个配置 × 41 条用例(双指标)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "bars.png", dpi=150)
    plt.close(fig)


def chart_radar(data, out_dir):
    angles = np.linspace(0, 2 * np.pi, len(CATEGORIES), endpoint=False).tolist()
    angles += angles[:1]  # 闭合
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"})
    for name in RADAR_CONFIGS:
        vals = [data[name]["summary"]["by_category"][c]["avg_answer_score"] for c in CATEGORIES]
        vals += vals[:1]
        lw = 2.5 if name == "best_stack_norerank" else 1.3
        ax.plot(angles, vals, label=name, linewidth=lw)
        ax.fill(angles, vals, alpha=0.06)
    ax.set_xticks(angles[:-1], CAT_LABELS, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_title("分方向答案分:配置间的'此消彼长'一眼可见", pad=24, fontsize=13)
    ax.legend(loc="upper right", bbox_to_anchor=(1.42, 1.1), fontsize=10)
    fig.savefig(out_dir / "radar.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def chart_heatmap(data, out_dir):
    names = list(data)
    case_ids = [c["id"] for c in data["baseline"]["cases"]]
    mat = np.array([[ {c["id"]: c["answer_score"] for c in data[n]["cases"]}[cid]
                      for n in names] for cid in case_ids])
    fig, ax = plt.subplots(figsize=(max(9, 0.85 * len(names)), 12))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(names)), names, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(case_ids)), case_ids, fontsize=7)
    ax.set_title("逐用例答案分热力图(绿=1 红=0)\n横向全绿=简单题,横向全红=待攻克,杂色=有区分度")
    fig.colorbar(im, shrink=0.5)
    fig.tight_layout()
    fig.savefig(out_dir / "heatmap.png", dpi=150)
    plt.close(fig)


def main():
    out_dir = PROJECT_ROOT / "results" / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = load_all()
    chart_bars(data, out_dir)
    chart_radar(data, out_dir)
    chart_heatmap(data, out_dir)
    print(f"3 张图已生成: {out_dir}")


if __name__ == "__main__":
    main()
