"""M41 任务二:去循环实验。humble_source 的 90% 被指为同源循环(58/58 determinable 案例
的 source_snippet 字面含答案模块名)。本脚本造 humble_source_masked:同样喂源码片段,但把
gold_complete 答案 token 在片段里**遮蔽**(▢▢▢),测模型在"源码结构在、具体答案被抹掉"时能否
真正推断出缺失模块——这才是去循环的"精确补全"真值。只在 determinable 子集(补全才有意义)上跑。
"""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT/"data"; OUT = ROOT/"results"/"dirty_large"
cases = json.load(open(D/"dirty_large.json", encoding="utf-8"))

HUMBLE = ("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整**——"
          "运行时动态导入、条件导入、反射、条件编译等依赖可能被遗漏或未标注其条件性。"
          "请**结合卡片与你自己对该项目的了解**作答,对静态分析可能遗漏/误标的依赖要主动指出并说明。\n\n")

def mask(snippet, toks):
    s = snippet
    for t in toks:
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', t):
            s = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(t)}(?![A-Za-z0-9_])", "▢▢▢", s)
        else:
            s = s.replace(t, "▢▢▢")
    return s

bundle = []
for c in cases:
    if not c["determinable"]:
        continue
    masked = mask(c["source_snippet"], c["gold_complete"])
    q = f"请准确、完整地说明 {c['project']}/{c['rel']} 实际会依赖/导入哪些模块。"
    prompt = (HUMBLE + c["card"] +
              f"\n\n[相关源码片段(部分标识符已用 ▢▢▢ 遮蔽)]\n{masked}" +
              f"\n\n问题:{q}\n请直接回答。")
    bundle.append({"id": c["id"], "difficulty": "hard", "category": c["dirty_type"],
                   "question": q, "gold": "/".join(c["gold_complete"][:2]),
                   "notes": "(去循环-masked)", "gen_prompt": prompt})

json.dump(bundle, open(OUT/"bundle_humble_source_masked.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"masked bundle(determinable 子集)N = {len(bundle)}")
print("示例遮蔽后片段:")
print("  原:", cases[0]["source_snippet"][:80] if cases[0]["determinable"] else "(skip)")
ex = next(b for b in bundle)
print("  masked gen_prompt 尾部:", ex["gen_prompt"][-220:])
