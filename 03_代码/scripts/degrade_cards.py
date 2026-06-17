"""M9 第二层:RAG 强度梯度 —— 在 prompt 文本层退化依赖图卡片的"边",
保持检索不变,只改卡片信息质量,隔离"卡片是否把答案喂到嘴边"这个混淆变量。

退化模式:
  incomplete  随机删边(每条边以 keep 概率保留 → 卡片不完整)
  noisy       随机改边(部分真边换成错文件 + 注入错边 → 卡片带噪声)

用法:python scripts/degrade_cards.py <prompts_name> <incomplete|noisy> [seed]
  读 results/prompts_<name>.json,写 results/prompts_<name>_<mode>.json
"""

import json
import random
import re
import sys

from _common import PROJECT_ROOT

R = PROJECT_ROOT / "results"

# 卡片里的"依赖边"行前缀(删/改只动这些行,不动定义类/函数那种事实)
EDGE_PREFIXES = [
    "它依赖(import)的仓库内文件: ",
    "它被这些文件依赖/使用(import 它的使用方): ",
    "它调用的仓库内函数: ",
    "它被这些函数调用: ",
    "它继承自: ",
    "继承它的子类: ",
]
PLACEHOLDERS = {"(无)", "(没有仓库内使用方)", "(没有仓库内调用方)", "(没有仓库内子类)", "(无基类)"}


def collect_pool(prompts):
    """从所有边行收集"同类替身池"(文件名池/符号名池),供 noisy 模式换错边。"""
    files, syms = set(), set()
    for p in prompts:
        for ln in p["prompt"].split("\n"):
            for pre in EDGE_PREFIXES:
                if ln.startswith(pre):
                    items = [x.strip() for x in ln[len(pre):].split(",") if x.strip() and x.strip() not in PLACEHOLDERS]
                    if ".py" in ln or "/" in ln or "依赖(import)" in pre or "依赖/使用" in pre:
                        files.update(i for i in items if "." in i or "/" in i)
                    else:
                        syms.update(items)
    return sorted(files), sorted(syms)


def degrade_line(pre, items, mode, rng, files, syms):
    pool = files if ("import" in pre or "依赖/使用" in pre or ".py" in (items[0] if items else "")) else syms
    if not pool:
        pool = files or syms
    if mode == "incomplete":
        kept = [it for it in items if rng.random() < 0.5]
        if not kept and items:                    # 至少删到非空原集变 1 条,保证"不完整"而非"清空"
            kept = [rng.choice(items)] if rng.random() < 0.5 else []
        new = kept
    else:  # noisy
        new = []
        for it in items:
            if rng.random() < 0.4:                # 40% 真边换成错边
                cand = [x for x in pool if x != it and x not in items]
                new.append(rng.choice(cand) if cand else it)
            else:
                new.append(it)
        # 注入 1-2 条额外错边
        for _ in range(rng.randint(1, 2)):
            cand = [x for x in pool if x not in new and x not in items]
            if cand:
                new.append(rng.choice(cand))
    if not new:
        return pre + "(无)"
    return pre + ", ".join(new)


def main():
    name, mode = sys.argv[1], sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 9
    assert mode in ("incomplete", "noisy")
    prompts = json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))
    files, syms = collect_pool(prompts)

    n_edge = 0
    for p in prompts:
        rng = random.Random(f"{seed}:{p['id']}")
        out_lines = []
        for ln in p["prompt"].split("\n"):
            hit = next((pre for pre in EDGE_PREFIXES if ln.startswith(pre)), None)
            if hit:
                items = [x.strip() for x in ln[len(hit):].split(",") if x.strip() and x.strip() not in PLACEHOLDERS]
                if items:
                    ln = degrade_line(hit, items, mode, rng, files, syms)
                    n_edge += 1
            out_lines.append(ln)
        p["prompt"] = "\n".join(out_lines)

    out = R / f"prompts_{name}_{mode}.json"
    out.write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name} -> {mode}: 退化 {n_edge} 条边行, {len(prompts)} prompt -> {out}")


if __name__ == "__main__":
    main()
