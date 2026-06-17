"""M6 任务二:从微调训练数据(flask/click 真实依赖 Q&A,与 werkzeug 隔离)
抽 ≥20 条**领域内** few-shot,建 pe_domain.yaml(= PE system + CoT + 领域 few-shot)。
对照 M4 的"通用 few-shot 有害",看领域 few-shot 是否反而有用。
"""

import json
import re

import yaml

from _common import PROJECT_ROOT
from build_pe_prompts import SYSTEM, COT

# 每类型取几条,凑 ≥20,覆盖六类型
WANT = {"间接依赖": 5, "哪些文件 import": 4, "直接依赖": 3, "继承自哪个文件": 3,
        "哪些类继承": 3, "定义在哪个文件": 3}


def main():
    picked = {k: [] for k in WANT}
    for ln in open(PROJECT_ROOT / "data" / "finetune_train.jsonl", encoding="utf-8"):
        s = json.loads(ln)
        user = s["messages"][0]["content"]
        q = user.split("[问题]")[-1].strip()
        a = s["messages"][1]["content"].strip()
        for key, n in WANT.items():
            if key in q and len(picked[key]) < n:
                picked[key].append({"question": q, "answer": a})
                break
        if all(len(picked[k]) >= WANT[k] for k in WANT):
            break

    fewshot = [ex for lst in picked.values() for ex in lst]
    data = {"name": "pe_domain", "system": SYSTEM, "few_shot": fewshot, "cot": True}
    (PROJECT_ROOT / "configs" / "prompts" / "pe_domain.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(f"领域 few-shot {len(fewshot)} 条(按类型 { {k: len(v) for k, v in picked.items()} })")
    print("-> configs/prompts/pe_domain.yaml")


if __name__ == "__main__":
    main()
