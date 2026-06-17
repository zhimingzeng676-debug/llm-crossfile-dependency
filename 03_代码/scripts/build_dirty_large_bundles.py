"""M38-40:从 dirty_large.json 生成 5 个条件的 gen 包。
条件:
  strict        — 只信卡片(基线对照)
  humble        — 承认卡片可能不全(M36 主条件,测识破率)
  baseline      — 无卡片纯参数知识
  humble_source — humble + 真实源码片段(机理实验:信息在上下文里时精确补全率会不会跳)
  humble_prompt — humble + 显式要求"具体指出哪个模块、什么机制"(机理实验:prompt 是不是杠杆)
中性问题(承接 M33,不在问题里枚举脏类型,识破靠 scaffold 不靠问题)。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT/"data"; OUT = ROOT/"results"/"dirty_large"; OUT.mkdir(parents=True, exist_ok=True)
cases = json.load(open(D/"dirty_large.json", encoding="utf-8"))

STRICT = ("你是代码依赖分析助手。请仅依据以下依赖卡片回答问题。卡片没有就说\"根据卡片没有找到\",不要臆造。\n\n")
HUMBLE = ("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整**——"
          "运行时动态导入、条件导入、反射、条件编译等依赖可能被遗漏或未标注其条件性。"
          "请**结合卡片与你自己对该项目的了解**作答,对静态分析可能遗漏/误标的依赖要主动指出并说明。\n\n")
BASE = ("你是代码依赖分析助手。请根据你对该项目的了解回答。不确定就说\"不确定\",不要臆造。\n\n")
PROMPT_HINT = ("\n\n注意:如果存在可选/条件/动态/反射依赖,请**具体指出是哪个模块**,"
               "以及**通过什么机制**(如 try/except ImportError、__import__、importlib、getattr、#ifdef、构建标签)产生。")

def q_of(c):
    return f"请准确、完整地说明 {c['project']}/{c['rel']} 实际会依赖/导入哪些模块。"

def gold_of(c):
    det = "可静态确定(源码里有,卡片漏标其条件性)" if c["determinable"] else "无法静态确定(运行时决定)"
    return (f"脏类型={c['dirty_type']}；具体脏依赖={'/'.join(c['gold_complete'][:2])}；"
            f"机制={'/'.join(c['gold_mech'][:2])}；{det}")

def entry(c, prompt):
    return {"id": c["id"], "difficulty": "hard", "category": c["dirty_type"],
            "question": q_of(c), "gold": gold_of(c), "notes": f"(脏-大样本 {c['dirty_type']})",
            "gen_prompt": prompt}

bundles = {"strict": [], "humble": [], "baseline": [], "humble_source": [], "humble_prompt": []}
for c in cases:
    q = q_of(c); card = c["card"]
    tail = f"\n\n问题:{q}\n请直接回答。"
    bundles["strict"].append(entry(c, STRICT + card + tail))
    bundles["humble"].append(entry(c, HUMBLE + card + tail))
    bundles["baseline"].append(entry(c, BASE + f"问题:{q}\n请直接回答。"))
    bundles["humble_source"].append(entry(c, HUMBLE + card + f"\n\n[相关源码片段]\n{c['source_snippet']}" + tail))
    bundles["humble_prompt"].append(entry(c, HUMBLE + card + PROMPT_HINT + tail))

for name, b in bundles.items():
    json.dump(b, open(OUT/f"bundle_{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("写出 5 条件 bundle,每个 N =", len(cases))
print("条件:", list(bundles))
print("示例 humble_source gen_prompt(截断):\n", bundles["humble_source"][0]["gen_prompt"][:600])
