"""M43 任务一:下游任务=影响分析(改文件X→谁依赖它需同步检查),用反向依赖。
错误卡片=真实反向依赖集漏掉 1 条边(模拟静态分析漏掉一个动态/条件导入方,真实会犯的错)。
4 条件:correct_card / wrong_card(strict信卡片) / wrong_card_humble / no_card(baseline)。
真值=完整反向依赖集(ast 独立导出,与RAG卡片解耦)。被漏的那条边="隐藏依赖方",重点追踪。
披露:漏的是静态边、用来"模拟"动态/条件导入被漏(werkzeug 反向边都是静态);如实标注是模拟。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
G = json.load(open(ROOT/"results"/"ast_edges_werkzeug.json", encoding="utf-8"))
OUT = ROOT/"results"/"downstream"; OUT.mkdir(parents=True, exist_ok=True)
rev = G["reverse"]

def tok(r):
    p = r.split("/")
    return p[-2] if p[-1] == "__init__.py" and len(p) >= 2 else p[-1][:-3]

cases = []
for f, imps in sorted(rev.items()):
    s = sorted({tok(d) for d in imps if tok(d) != tok(f)})
    if len(s) >= 2:
        dropped = s[len(s)//2]               # 确定性挑中间一条作"被漏的隐藏依赖方"
        wrong = [x for x in s if x != dropped]
        cases.append({"file": f, "gold_full": s, "dropped": dropped, "card_wrong": wrong})

Q = "在 werkzeug 项目中,如果要修改文件 {f} 的对外接口,项目内有哪些文件直接依赖它、改动时需要同步检查?请列出文件名(模块名),逗号分隔。"
def card(deps): return "[依赖卡片] 项目内直接 import 该文件的文件(静态分析): " + ", ".join(deps)

NEU = "你是代码依赖分析助手。请依据以下依赖卡片回答(卡片列出了依赖该文件的项目内文件)。\n\n"
HUM = ("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整**——"
       "通过动态导入/条件导入依赖该文件的文件可能被漏掉、未列出。请**结合卡片与你对 werkzeug 的了解**回答,"
       "若怀疑还有未列出的依赖方,请主动指出并提醒需要进一步核查。\n\n")
BASE = "你是代码依赖分析助手。请根据你对 werkzeug 源码的了解回答。不确定就说\"不确定\",不要臆造。\n\n"

def entry(c, cond):
    q = Q.format(f=c["file"]); tail = f"\n\n问题:{q}\n请直接回答。"
    if cond == "correct_card":
        gp = NEU + card(c["gold_full"]) + tail
    elif cond == "wrong_card":
        gp = NEU + card(c["card_wrong"]) + tail
    elif cond == "wrong_card_humble":
        gp = HUM + card(c["card_wrong"]) + tail
    else:  # no_card
        gp = BASE + f"问题:{q}\n请直接回答。"
    return {"id": c["file"], "difficulty": "hard", "category": "impact",
            "question": q, "gold": ", ".join(c["gold_full"]), "dropped": c["dropped"],
            "notes": "(downstream impact)", "gen_prompt": gp}

CONDS = ["correct_card", "wrong_card", "wrong_card_humble", "no_card"]
for cond in CONDS:
    json.dump([entry(c, cond) for c in cases], open(OUT/f"bundle_{cond}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
json.dump({c["file"]: {"gold_full": c["gold_full"], "dropped": c["dropped"], "card_wrong": c["card_wrong"]}
           for c in cases}, open(OUT/"goldmap.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"下游影响分析案例 N={len(cases)}(|反向依赖|>=2,各漏1条边)")
print("反向集大小:", sorted(len(c["gold_full"]) for c in cases))
print("示例 wrong_card:", entry(cases[0], "wrong_card")["gen_prompt"][:240])
print("  gold_full:", cases[0]["gold_full"], "| dropped:", cases[0]["dropped"])
