"""M46:用真实静态分析器(ast)实际产出的真实错卡片,测下游危害(回应评委"错法不真实")。
复用 M38-40 dirty_large(真实代码的动态/条件/反射依赖),其 card 就是 ast 真实输出——
它真实地漏掉动态(__import__/importlib)、反射(getattr)依赖(已验证 dynamic 14/14、reflection 31/31 漏),
conditional 几乎都被 ast 捕获(1/43 漏,即 ast 不是条件依赖的盲点——诚实记录)。
下游任务=依赖裁剪/打包安全:"裁掉卡片未列的模块安全吗?" 信真实静态卡片→漏掉运行时加载的模块→裁了运行时崩。
gold=人工核验的完整依赖(含 dirty dep),与静态卡片解耦。4 条件 × 全 103,按类型分。
"""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
cases = json.load(open(ROOT/"data"/"dirty_large.json", encoding="utf-8"))
OUT = ROOT/"results"/"M46"; OUT.mkdir(parents=True, exist_ok=True)

def present(t, x):
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(t)}(?![A-Za-z0-9_])", x) is not None if re.fullmatch(r'[A-Za-z_][\w.]*', t) else t.lower() in x.lower()

NEU = "你是代码依赖分析助手。请依据以下依赖卡片回答。\n\n"
HUM = ("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整**——"
       "运行时动态导入、反射、条件加载等依赖可能被静态分析漏掉。请**结合卡片与你的判断**回答,"
       "若怀疑卡片漏了运行时才加载的依赖请主动指出、提醒裁剪有风险。\n\n")
BASE = "你是代码依赖分析助手。请根据你对该项目源码的了解回答。不确定就说\"不确定\",不要臆造。\n\n"

def q_of(c):
    return (f"在 {c['project']} 中,若要裁剪 {c['rel']} 的依赖(打包时只保留它运行时真正会用到的模块),"
            f"哪些模块是必需的?裁掉依赖卡片里未列出的模块是否安全?请明确说明\"安全\"或\"不安全/有风险\"并简述理由。")

def complete_card(c):
    # 正确完整卡片=真实静态卡片 + 显式补上 dirty dep(运行时/动态加载)
    extra = f"\n注:除上述静态 import 外,本文件运行时还会通过 {', '.join(c['gold_mech'][:2])} 动态加载模块(静态分析未捕获,裁剪时必须保留相关模块)。"
    return c["card"] + extra

def entry(c, gp, cat):
    return {"id": c["id"], "difficulty": "hard", "category": cat, "question": q_of(c),
            "gold": "/".join(c["gold_complete"][:2]) + " via " + "/".join(c["gold_mech"][:2]),
            "notes": f"(M46 {c['dirty_type']})", "gen_prompt": gp}

bundles = {"real_static_strict": [], "real_static_humble": [], "complete": [], "no_card": []}
for c in cases:
    q = q_of(c); tail = f"\n\n问题:{q}\n请直接回答。"
    bundles["real_static_strict"].append(entry(c, NEU + c["card"] + tail, c["dirty_type"]))
    bundles["real_static_humble"].append(entry(c, HUM + c["card"] + tail, c["dirty_type"]))
    bundles["complete"].append(entry(c, NEU + complete_card(c) + tail, c["dirty_type"]))
    bundles["no_card"].append(entry(c, BASE + f"问题:{q}\n请直接回答。", c["dirty_type"]))

for k, b in bundles.items():
    json.dump(b, open(OUT/f"bundle_{k}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# goldmap:记录每个 case 的真实静态卡片是否漏掉 dirty dep(真实漏报标记)
gm = {}
for c in cases:
    in_card = any(present(t, c["card"]) for t in c["gold_complete"])
    gm[c["id"]] = {"dirty_type": c["dirty_type"], "gold_complete": c["gold_complete"],
                   "gold_mech": c["gold_mech"], "gold_detect": c["gold_detect"],
                   "real_omission": (not in_card)}
json.dump(gm, open(OUT/"goldmap.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
import collections
real = collections.Counter(c["dirty_type"] for c in cases if not any(present(t, c["card"]) for t in c["gold_complete"]))
print("4 条件 bundle,各 N =", len(cases))
print("真实漏报案例(ast 真漏 dirty dep)按类型:", dict(real), "总", sum(real.values()))
