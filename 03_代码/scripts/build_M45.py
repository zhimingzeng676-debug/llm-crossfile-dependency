"""M45:把 M44 两个边界探扎实(M41 红线:控制实验排除替代解释,不挑口径)。
边界A(漏报/误报不对称)是否任务依赖:用 leaf 文件(无内部依赖方=真安全删)+ 假卡片,
  在 T1影响分析(误报=多报假影响,浪费) vs T2安全删除(误报=误判"不安全",过度拦截 该删不敢删) 上分别测。
边界B(humble保护 vs 危险程度反相关)的真实机理:2×2 卡片长度{短,长}×完整性{对,缺},
  卡片长度对齐——若 humble hedge 只随长度(短卡片不论对错都hedge)=长度反射,非完整性检测(更尖锐的诚实结论)。
真值由 ast/独立图导出。零 LLM 打分。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/"results"/"M45"; OUT.mkdir(parents=True, exist_ok=True)

def tok_pkg(r):
    p = r.split("/"); return p[-2] if p[-1] == "__init__.py" and len(p) >= 2 else p[-1].rsplit(".",1)[0]
def load(proj):
    if proj == "wz":
        g = json.load(open(ROOT/"results"/"ast_edges_werkzeug.json", encoding="utf-8")); tf = tok_pkg
        fwd, rev = g["forward"], g["reverse"]
    else:  # cpy
        e = json.load(open(ROOT/"results"/"cpy"/"edges.json", encoding="utf-8")); tf = lambda r: r.split("/")[-1].rsplit(".",1)[0]
        fwd, rev = e["pyfwd"], e["pyrev"]
    F = {f: sorted({tf(d) for d in v if tf(d) != tf(f)}) for f, v in fwd.items()}
    R = {f: sorted({tf(d) for d in v if tf(d) != tf(f)}) for f, v in rev.items()}
    allt = sorted({tf(x) for x in set(fwd) | set(rev)})
    leaves = [f for f in fwd if f not in rev]  # 无内部依赖方=真安全删
    return F, R, allt, leaves, tf
PN = {"wz": "werkzeug 项目", "cpy": "CPython 项目"}

NEU = "你是代码依赖分析助手。请依据以下依赖卡片回答。\n\n"
HUM = ("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整或有误**——"
       "动态/条件导入等可能被漏标或误标。请**结合卡片与你的判断**回答,若怀疑卡片有遗漏/错误请主动指出并提醒核查。\n\n")

def q_T1(P, F): return f"在 {P} 中,如果要修改文件 {F} 的对外接口,项目内有哪些文件直接依赖它、改动时需要同步检查?请列出文件名(模块名),逗号分隔;若无则回答\"无\"。"
def q_T2(P, F): return f"在 {P} 中,删除文件 {F} 是否安全?如果不安全,项目内哪些文件依赖它、会受影响?请先明确回答\"安全\"或\"不安全\",再列出受影响文件。"
def card_rev(deps): return "[依赖卡片] 项目内直接 import 该文件的文件(静态分析): " + (", ".join(deps) if deps else "(无)")

def entry(F, q, card, mode, cat="dep"):
    head = HUM if mode == "humble" else NEU
    gp = head + card + f"\n\n问题:{q}\n请直接回答。"
    return {"id": F, "difficulty": "hard", "category": cat, "question": q, "notes": f"({mode})", "gen_prompt": gp}

bundles = {}; goldmaps = {}; manifest = {}

# ===== 边界A:leaf 文件 over-report,T1 vs T2 =====
for proj, cap in [("cpy", 30), ("wz", 7)]:
    Fmap, Rmap, allt, leaves, tf = load(proj); P = PN[proj]
    leaves = sorted(leaves)[:cap]
    for F in leaves: pass
    fakes_for = {F: [t for t in allt if t != tf(F)][:2] for F in leaves}  # 2 个真实但非依赖方=假边
    for task, qf in [("T1", q_T1), ("T2", q_T2)]:
        for mode in ["strict", "humble"]:
            key = f"A_{proj}_{task}_over_{mode}"
            bundles[key] = [entry(F, qf(P, F), card_rev(fakes_for[F]), mode) for F in leaves]
            goldmaps[key] = {F: {"gold_rev": [], "fake": fakes_for[F], "true_safe": True} for F in leaves}
            manifest[key] = {"kind": "boundaryA_overreport", "proj": proj, "task": task, "mode": mode, "n": len(leaves)}
        # correct 对照(诚实卡片:无人依赖)
        key = f"A_{proj}_{task}_correct"
        bundles[key] = [entry(F, qf(P, F), card_rev([]), "strict") for F in leaves]
        goldmaps[key] = {F: {"gold_rev": [], "fake": [], "true_safe": True} for F in leaves}
        manifest[key] = {"kind": "boundaryA_correct", "proj": proj, "task": task, "mode": "strict", "n": len(leaves)}

# ===== 边界B:2×2 卡片长度×完整性(cpy,T1)=====
Fmap, Rmap, allt, leaves, tf = load("cpy"); P = PN["cpy"]
by = {}
for F, r in Rmap.items():
    by.setdefault(len(r), []).append((F, r))
def pick(sizes, n):
    out=[]
    for s in sizes:
        out += sorted(by.get(s, []))[:n]
    return out
SHORT_LEN, LONG_LEN = 2, 8
cells = {
    "shortC": [(F, r, r) for F, r in pick([2], 20)],                                  # 真2,卡片全2(短/对)
    "shortI": [(F, r, r[:SHORT_LEN]) for F, r in pick([8,9,10,11,12], 6)][:20],       # 真>=8,卡片truncate到2(短/缺)
    "longC":  [(F, r, r) for F, r in pick([7,8,9], 8)][:20],                          # 真7-9,卡片全(长/对)
    "longI":  [(F, r, r[:LONG_LEN]) for F, r in pick([14,15,17,18,20,21,22,23], 3)][:20],  # 真>=14,卡片truncate到8(长/缺)
}
for cell, items in cells.items():
    for mode in ["strict", "humble"]:
        key = f"B_{cell}_{mode}"
        b = []; gm = {}
        for F, full, shown in items:
            dropped = [x for x in full if x not in shown]
            b.append(entry(F, q_T1(P, F), card_rev(shown), mode))
            gm[F] = {"gold_rev": full, "shown": shown, "dropped": dropped, "card_len": len(shown)}
        bundles[key] = b; goldmaps[key] = gm
        manifest[key] = {"kind": "boundaryB", "cell": cell, "mode": mode, "n": len(items), "card_len": len(items[0][2]) if items else 0}

for k, b in bundles.items():
    json.dump(b, open(OUT/f"bundle_{k}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(goldmaps, open(OUT/"goldmaps.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(manifest, open(OUT/"manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("边界A leaf 数: cpy", len([k for k in manifest if k.startswith('A_cpy')]), "wz", len([k for k in manifest if k.startswith('A_wz')]))
print("边界B 各cell n:", {c: len(cells[c]) for c in cells})
print("总 bundle:", len(bundles))
for k, m in manifest.items():
    if k.startswith("B_") and m["mode"]=="humble": print(f"  {k}: n={m['n']} card_len={m['card_len']}")
