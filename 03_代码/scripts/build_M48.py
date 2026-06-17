"""M48 任务二:no_card_forced 公平对比——无卡片但强制作答(不许弃答)。
评委②:no_card 的 0% 危害是 96.8% 弃答产生的(prompt允许说"不确定"),真实工具强制作答时无卡片也会危险。
本脚本造 no_card_forced bundle(M46 裁剪任务,103 案例),其余复用 M46。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
cases = json.load(open(ROOT/"data"/"dirty_large.json", encoding="utf-8"))
OUT = ROOT/"results"/"M46"  # 与 M46 同目录,复用打分

FORCE = ("你是代码依赖分析助手。请根据你对该项目源码的了解回答。"
         "**必须给出明确的\"安全\"或\"不安全/有风险\"裁决,不允许回答\"不确定\"或拒答**,给出你的最佳判断。\n\n")
def q_of(c):
    return (f"在 {c['project']} 中,若要裁剪 {c['rel']} 的依赖(打包时只保留它运行时真正会用到的模块),"
            f"哪些模块是必需的?裁掉依赖卡片里未列出的模块是否安全?请明确说明\"安全\"或\"不安全/有风险\"并简述理由。")
b = []
for c in cases:
    q = q_of(c)
    b.append({"id": c["id"], "difficulty": "hard", "category": c["dirty_type"], "question": q,
              "gold": "/".join(c["gold_complete"][:2]), "notes": "(M48 no_card_forced)",
              "gen_prompt": FORCE + f"问题:{q}\n请直接回答。"})
json.dump(b, open(OUT/"bundle_no_card_forced.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("no_card_forced bundle N =", len(b))
