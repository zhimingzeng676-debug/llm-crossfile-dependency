"""M42 任务一+二:构造"见过 vs 没见过"切分,测结构化卡片增益里"参数记忆 vs 上下文结构"占比。
切分=标识符系统性改名(构造b):同一份 werkzeug 依赖结构,seen=真名(模型背过)、unseen=改名(等价但陌生,
结构不变只让"背诵"失效)。唯一变量=模型是否背过这些名字。
2×2:{seen,unseen}×{baseline 无卡片, full 结构化卡片}。judge-independent 关键词召回打分。
真值由 ast 独立依赖图导出(与 RAG 卡片解耦)。
披露:本切分用改名(构造b);未用(a)训练截止后新项目(本地无)、(c)纯人造。改名局限=只让表层 token 陌生,
模型仍可能靠依赖结构的统计模式;不等于真实私有代码(私有代码连结构习惯也可能不同)。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
G = json.load(open(ROOT/"results"/"ast_edges_werkzeug.json", encoding="utf-8"))
OUT = ROOT/"results"/"memstruct"; OUT.mkdir(parents=True, exist_ok=True)
fwd, rev = G["forward"], G["reverse"]

def tok(relpath):
    p = relpath.split("/")
    if p[-1] == "__init__.py":
        return p[-2] if len(p) >= 2 else "werkzeug"  # 顶层 __init__ -> 包根
    return p[-1][:-3]  # 文件stem

# 名字宇宙:所有路径组件(目录名 + 文件stem,排除 __init__)
names = set()
for rel in set(fwd) | set(rev) | {x for v in fwd.values() for x in v} | {x for v in rev.values() for x in v}:
    for comp in rel.split("/"):
        if comp == "__init__.py": continue
        names.add(comp[:-3] if comp.endswith(".py") else comp)
# 确定性改名(无随机):排序后 u01..uNN
rename = {n: f"u{i:02d}" for i, n in enumerate(sorted(names))}
def rn_path(relpath):
    return "/".join("__init__.py" if c == "__init__.py" else
                    (rename[c[:-3]] + ".py" if c.endswith(".py") else rename[c])
                    for c in relpath.split("/"))
def rn_tok(t): return rename.get(t, t)

cases = []  # (cid, kind, real_path, gold[real toks])
fid = rid = 0
for f, deps in sorted(fwd.items()):
    g = sorted({tok(d) for d in deps if tok(d) != tok(f)})
    if 2 <= len(g) <= 7:
        cases.append((f"FW{fid:02d}", "forward", f, g)); fid += 1
for f, imps in sorted(rev.items()):
    g = sorted({tok(d) for d in imps if tok(d) != tok(f)})
    if 2 <= len(g) <= 7:
        cases.append((f"RV{rid:02d}", "reverse", f, g)); rid += 1

def q_of(kind, path, proj):
    if kind == "forward":
        return f"在 {proj} 中,文件 {path} 直接依赖(import)了哪些项目内模块?只列模块名,逗号分隔。"
    return f"在 {proj} 中,项目内哪些文件直接 import 了 {path}?只列文件名(模块名),逗号分隔。"
def card_of(kind, path, gold):
    if kind == "forward":
        return f"[依赖卡片] 文件 {path}\n它直接 import 的项目内模块(静态分析): {', '.join(gold)}\n(注:静态依赖图导出)"
    return f"[依赖卡片] 文件 {path}\n项目内直接 import 它的文件(静态分析): {', '.join(gold)}\n(注:静态依赖图导出)"

SYS = "你是代码依赖分析助手。"
def entry(cid, kind, path, gold, full, proj):
    q = q_of(kind, path, proj)
    if full:
        gp = SYS + "请依据以下依赖卡片回答。\n\n" + card_of(kind, path, gold) + f"\n\n问题:{q}\n请直接回答。"
    else:
        gp = SYS + "请根据你对该项目的了解回答。不确定就说\"不确定\",不要臆造。\n\n" + f"问题:{q}\n请直接回答。"
    return {"id": cid, "difficulty": "medium", "category": kind, "question": q,
            "gold": ", ".join(gold), "notes": "(memvsstruct)", "gen_prompt": gp}

bundles = {"seen_baseline": [], "seen_full": [], "unseen_baseline": [], "unseen_full": []}
goldmap = {}  # cid -> {seen:[...], unseen:[...]}
for cid, kind, f, g in cases:
    # seen = 真名 + 点名 werkzeug(让参数记忆能engage)
    bundles["seen_baseline"].append(entry(cid, kind, f, g, full=False, proj="werkzeug 项目"))
    bundles["seen_full"].append(entry(cid, kind, f, g, full=True, proj="werkzeug 项目"))
    # unseen = 改名 + 匿名项目(无记忆可依)
    rf = rn_path(f); rg = [rn_tok(x) for x in g]
    bundles["unseen_baseline"].append(entry(cid, kind, rf, rg, full=False, proj="某 Python 项目"))
    bundles["unseen_full"].append(entry(cid, kind, rf, rg, full=True, proj="某 Python 项目"))
    goldmap[cid] = {"kind": kind, "seen_path": f, "unseen_path": rf, "seen_gold": g, "unseen_gold": rg}

for name, b in bundles.items():
    json.dump(b, open(OUT/f"bundle_{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(goldmap, open(OUT/"goldmap.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
import collections
print("案例:", len(cases), dict(collections.Counter(c[1] for c in cases)))
print("改名表大小:", len(rename), "例:", dict(list(rename.items())[:5]))
print("示例 seen_full:", bundles["seen_full"][0]["gen_prompt"][:200])
print("示例 unseen_full:", bundles["unseen_full"][0]["gen_prompt"][:200])
print("写出 4 bundle + goldmap ->", OUT)
