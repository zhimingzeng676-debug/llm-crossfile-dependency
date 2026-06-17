"""PE 第四维度:输出后处理(过滤/排序/去重 + 检索接地补全)。

对"列出多个依赖"类问题,模型常漏列。后处理思路(只用模型已拿到的检索上下文,
不看 ground truth):从 prompt 里的[依赖图卡片]抽出权威的"依赖/被依赖/子类"清单,
与模型答案做并集去重,补回漏列项。这是合法的后处理(基于检索到的结构化数据)。

用法:python scripts/postprocess.py <config_name>
  读 results/prompts_<name>.json(含检索上下文)+ results/answers_<name>.json,
  写 results/answers_<name>_pp.json + 复制 prompts 供 judge 复用。
"""

import json
import re
import sys

from _common import PROJECT_ROOT

# 卡片里"清单"行的标识
CARD_LINES = [
    "它被这些文件依赖/使用",   # 反向依赖
    "它依赖(import)的仓库内文件",  # 正向依赖
    "继承它的子类",            # 反向继承
]
PATH_RE = re.compile(r"[A-Za-z_][\w/]*\.py|\b[A-Z]\w+\b")


def extract_card_lists(prompt: str) -> list[str]:
    """从 prompt 的依赖卡片里抽出权威清单项(文件路径 / 类名)。"""
    items = []
    for line in prompt.splitlines():
        if any(tag in line for tag in CARD_LINES):
            # 取冒号后的部分
            rhs = line.split(":", 1)[-1] if ":" in line else line.split(":", 1)[-1]
            for tok in re.split(r"[,,、\s]+", rhs):
                tok = tok.strip().strip("[]()。.")
                if tok.endswith(".py") or (tok and tok[0].isupper() and len(tok) > 2):
                    items.append(tok)
    # 去重保序
    seen = []
    for it in items:
        if it not in seen:
            seen.append(it)
    return seen


def postprocess(answer: str, card_items: list[str]) -> str:
    """去重模型答案中的重复项,并把卡片里有、答案没提到的项补回。"""
    if not card_items:
        return answer
    missing = [it for it in card_items if it not in answer]
    if not missing:
        return answer
    add = "\n[后处理补全 — 依据检索到的依赖卡片清单]: " + ", ".join(missing)
    return answer + add


def main():
    name = sys.argv[1]
    R = PROJECT_ROOT / "results"
    pmeta = {p["id"]: p for p in json.load(open(R / f"prompts_{name}.json", encoding="utf-8"))}
    answers = json.load(open(R / f"answers_{name}.json", encoding="utf-8"))

    # 选择性:只对"列出多个"类问题后处理(反向/正向依赖,或问"哪些...")。
    # 单答案题(符号定位/间接依赖的中间节点)补全只会塞噪声,跳过。
    def is_list_q(p):
        return p["category"] in ("reverse_dep", "forward_dep") or "哪些" in p["question"]

    out = []
    touched = 0
    for a in answers:
        cid = a["id"]
        p = pmeta.get(cid, {})
        if p and is_list_q(p):
            items = extract_card_lists(p["prompt"])
            new = postprocess(a["answer"], items)
        else:
            new = a["answer"]
        if new != a["answer"]:
            touched += 1
        out.append({"id": cid, "answer": new})

    tag = f"{name}_pp"
    json.dump(out, open(R / f"answers_{tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # prompts 文件给 judge 复用(同名换 tag)
    json.dump(json.load(open(R / f"prompts_{name}.json", encoding="utf-8")),
              open(R / f"prompts_{tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{tag}: 后处理补全了 {touched}/{len(out)} 条 -> answers_{tag}.json")


if __name__ == "__main__":
    main()
