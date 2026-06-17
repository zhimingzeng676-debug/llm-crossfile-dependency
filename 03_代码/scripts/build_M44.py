"""M44:把"错卡片下游危害"做厚。一次只变一个轴(从 M43 基线 werkzeug/T1/drop1 出发)。
- 项目轴(T1,drop1):werkzeug(M43复用)/CPython/flask/gson(跨语言)
- 任务轴(werkzeug,drop1):T1 影响分析 / T2 安全删除 / T3 正向同步
- 错法轴(werkzeug,T1):drop1(M43)/ dropN(漏多条)/ overreport(误报假边)
真值由独立依赖图导出(ast/regex,与RAG卡片解耦)。错法真实(漏边=静态漏动态/条件依赖方;误报=静态误判)。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/"results"/"M44"; OUT.mkdir(parents=True, exist_ok=True)

# ---- 加载各项目依赖图,统一成 fwd/rev(token级)----
def tok_pkg(rel):
    p = rel.split("/"); return p[-2] if p[-1] == "__init__.py" and len(p) >= 2 else p[-1].rsplit(".",1)[0]

def load_graph(proj):
    if proj == "wz":
        g = json.load(open(ROOT/"results"/"ast_edges_werkzeug.json", encoding="utf-8")); tf = tok_pkg
    elif proj == "flask":
        g = json.load(open(ROOT/"results"/"ast_edges_flask.json", encoding="utf-8")); tf = tok_pkg
    elif proj == "gson":
        g = json.load(open(ROOT/"results"/"edges_gson.json", encoding="utf-8")); tf = lambda r: r.split("/")[-1].rsplit(".",1)[0]
    elif proj == "cpy":
        e = json.load(open(ROOT/"results"/"cpy"/"edges.json", encoding="utf-8"))
        g = {"forward": e["pyfwd"], "reverse": e["pyrev"]}; tf = lambda r: r.split("/")[-1].rsplit(".",1)[0]
    fwd = {f: sorted({tf(d) for d in v if tf(d) != tf(f)}) for f, v in g["forward"].items()}
    rev = {f: sorted({tf(d) for d in v if tf(d) != tf(f)}) for f, v in g["reverse"].items()}
    allt = sorted({tf(x) for x in set(g["forward"]) | set(g["reverse"])})
    return fwd, rev, allt

PROJ_NAME = {"wz": "werkzeug 项目", "flask": "flask 项目", "gson": "google-gson 项目", "cpy": "CPython 项目"}

# ---- 任务定义:用 reverse(T1/T2) 或 forward(T3) ----
def gold_set(proj, task, F, fwd, rev):
    return fwd.get(F, []) if task == "T3" else rev.get(F, [])

def question(proj, task, F):
    P = PROJ_NAME[proj]
    if task == "T1":
        return f"在 {P} 中,如果要修改文件 {F} 的对外接口,项目内有哪些文件直接依赖它、改动时需要同步检查?请列出文件名(模块名),逗号分隔。"
    if task == "T2":
        return f"在 {P} 中,删除文件 {F} 是否安全?如果不安全,项目内哪些文件依赖它、会受影响?请先回答安全/不安全,再列出受影响的文件名,逗号分隔。"
    if task == "T3":
        return f"在 {P} 中,文件 {F} 直接依赖(import)了哪些项目内模块?如果这些被依赖模块被修改,{F} 需同步检查——请列出 {F} 依赖的所有模块,逗号分隔。"

def card_text(task, deps):
    if task == "T3":
        return "[依赖卡片] 该文件直接 import 的项目内模块(静态分析): " + ", ".join(deps)
    return "[依赖卡片] 项目内直接 import 该文件的文件(静态分析): " + ", ".join(deps)

NEU = "你是代码依赖分析助手。请依据以下依赖卡片回答。\n\n"
HUM = ("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整或有误**——"
       "动态/条件导入、跨语言边等可能被漏标或误标。请**结合卡片与你的判断**回答,若怀疑卡片有遗漏/错误请主动指出并提醒核查。\n\n")
BASE = "你是代码依赖分析助手。请根据你对该项目源码的了解回答。不确定就说\"不确定\",不要臆造。\n\n"

def make_card(gold, error, allt, F):
    """返回 (card_deps, dropped_list, fake_list)。"""
    if error == "correct":
        return gold, [], []
    if error == "drop1":
        d = gold[len(gold)//2]; return [x for x in gold if x != d], [d], []
    if error == "dropN":
        k = max(1, len(gold)//2); dl = gold[:k]  # 漏掉前半
        return [x for x in gold if x not in dl], dl, []
    if error == "overreport":
        fakes = [t for t in allt if t not in gold and t != tok_pkg(F)][:2]
        return gold + fakes, [], fakes
    return gold, [], []

def entry(proj, task, F, gold, cond, error, allt):
    q = question(proj, task, F); tail = f"\n\n问题:{q}\n请直接回答。"
    if cond == "nocard":
        gp = BASE + f"问题:{q}\n请直接回答。"; card_deps, dropped, fake = gold, [], []
    else:
        card_deps, dropped, fake = make_card(gold, error if cond != "correct" else "correct", allt, F)
        head = HUM if cond == "humble" else NEU
        gp = head + card_text(task, card_deps) + tail
    return ({"id": F, "difficulty": "hard", "category": task, "question": q,
             "gold": ", ".join(gold), "notes": f"({proj}/{task}/{error}/{cond})", "gen_prompt": gp},
            {"gold_full": gold, "dropped": dropped, "fake": fake})

# ---- 实验矩阵 ----
EXPERIMENTS = [
    # (key, proj, task, error)  —— 项目轴
    ("wz_T1_drop1", "wz", "T1", "drop1"),   # = M43(复用答案,这里只为完整 goldmap)
    ("cpy_T1_drop1", "cpy", "T1", "drop1"),
    ("flask_T1_drop1", "flask", "T1", "drop1"),
    ("gson_T1_drop1", "gson", "T1", "drop1"),
    # 任务轴
    ("wz_T2_drop1", "wz", "T2", "drop1"),
    ("wz_T3_drop1", "wz", "T3", "drop1"),
    # 错法轴
    ("wz_T1_dropN", "wz", "T1", "dropN"),
    ("wz_T1_overreport", "wz", "T1", "overreport"),
]
CAP = {"cpy": 22, "gson": 22, "flask": 16}

manifest = {}; goldmaps = {}
for key, proj, task, error in EXPERIMENTS:
    fwd, rev, allt = load_graph(proj)
    src = fwd if task == "T3" else rev
    cases = []
    for F in sorted(src):
        g = gold_set(proj, task, F, fwd, rev)
        if len(g) >= 2: cases.append((F, g))
    cases = cases[:CAP.get(proj, 28)]
    gm = {}
    # goldmap 一次性按"错法"算 dropped/fake(与 condition 无关,供打分用)
    for F, g in cases:
        _, ddl, ffl = make_card(g, error, allt, F)
        gm[F] = {"gold_full": g, "dropped": ddl, "fake": ffl}
    conds = ["correct", "wrong", "humble", "nocard"]
    # 错法轴只新生成 wrong/humble(correct/nocard 与 wz_T1_drop1 同,复用 M43)
    if key in ("wz_T1_dropN", "wz_T1_overreport"):
        conds = ["wrong", "humble"]
    for cond in conds:
        bundle = []
        for F, g in cases:
            e, _ = entry(proj, task, F, g, cond, error, allt)
            bundle.append(e)
        json.dump(bundle, open(OUT/f"bundle_{key}_{cond}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    goldmaps[key] = gm
    manifest[key] = {"proj": proj, "task": task, "error": error, "n": len(cases), "conds": conds}

json.dump(goldmaps, open(OUT/"goldmaps.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(manifest, open(OUT/"manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in manifest.items():
    print(f"  {k:20s} proj={v['proj']:6s} task={v['task']} error={v['error']:10s} n={v['n']} conds={v['conds']}")
print("写出 bundles + goldmaps + manifest ->", OUT)
