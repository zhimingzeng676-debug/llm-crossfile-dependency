"""M45 打分(judge-independent 零 LLM)。
边界A(leaf 文件,真安全删):
  - over-report 危害随任务变:T1 影响分析→false_impact(照抄假依赖方=多报影响,浪费);
    T2 安全删除→over_block(误判"不安全"=该删不敢删)。correct 对照给 baseline。
  - 对比 under-report(M44:漏报→危险)得完整不对称图谱。
边界B(2×2 卡片长度×完整性):hedge 率随长度还是随完整性?
  若 hedge 只随长度(短卡片不论对/缺都hedge)=长度反射,非完整性检测。
"""
import json, re, sys
from pathlib import Path
# (统计单元=逐用例配对;本文件按cell报率,无需 ttest)
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT/"results"/"M45"
manifest = json.load(open(D/"manifest.json", encoding="utf-8"))
gms = json.load(open(D/"goldmaps.json", encoding="utf-8"))

def present(tok, text):
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', tok):
        t = re.escape(tok); return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None
    return tok.lower() in text.lower()
HEDGE = ["可能不全","可能不完整","不完整","可能还有","可能存在","可能遗漏","遗漏","未列全","不一定全",
         "进一步核查","需要核查","需核查","建议核查","动态","条件导入","未列出","可能漏","还可能",
         "其他文件","不确定是否","无法确定是否完整","审慎","可能有误","误标","无法准确","似乎并不","只显示","仅显示","只列"]
def hedge_hit(t): return any(h in t for h in HEDGE)
def says_unsafe(t):
    return ("不安全" in t) or ("不建议删除" in t) or ("不能删除" in t) or ("不可删除" in t)
def says_safe(t):
    return ("安全" in t and "不安全" not in t)

def runs(key): return json.load(open(D/f"ans_{key}.json", encoding="utf-8"))["runs"]

def scoreA(key):
    gm = gms[key]; m = manifest[key]; task = m["task"]
    per = {}
    for run in runs(key):
        for x in run:
            g = gm[x["id"]]; a = x["answer"]; fake = g["fake"]
            fparrot = (sum(1 for f in fake if present(f, a))/len(fake)) if fake else 0.0
            overblock = 1 if says_unsafe(a) else 0
            safe = 1 if says_safe(a) else 0
            per.setdefault(x["id"], {"fp": [], "ob": [], "safe": []})
            per[x["id"]]["fp"].append(fparrot); per[x["id"]]["ob"].append(overblock); per[x["id"]]["safe"].append(safe)
    agg = {k: round(sum(sum(c[k])/len(c[k]) for c in per.values())/len(per), 3) for k in ["fp","ob","safe"]}
    return agg

def scoreB(key):
    gm = gms[key]
    per = {}
    for run in runs(key):
        for x in run:
            g = gm[x["id"]]; a = x["answer"]; dropped = g["dropped"]; gold = g["gold_rev"]
            rec = sum(1 for k in gold if present(k, a))/len(gold) if gold else 0
            hed = 1 if hedge_hit(a) else 0
            miss = any(not present(d, a) for d in dropped) if dropped else False
            danger = 1 if (dropped and rec >= 0.3 and miss and not hed) else 0
            per.setdefault(x["id"], {"hed": [], "dang": [], "rec": []})
            per[x["id"]]["hed"].append(hed); per[x["id"]]["dang"].append(danger); per[x["id"]]["rec"].append(rec)
    agg = {k: round(sum(sum(c[k])/len(c[k]) for c in per.values())/len(per), 3) for k in ["hed","dang","rec"]}
    agg["_per"] = {i: sum(c["hed"])/len(c["hed"]) for i, c in per.items()}
    return agg

report = {"A": {}, "B": {}}
for key, m in manifest.items():
    if not (D/f"ans_{key}.json").exists(): continue
    if m["kind"].startswith("boundaryA"): report["A"][key] = scoreA(key)
    elif m["kind"] == "boundaryB": report["B"][key] = scoreB(key)

print("=== 边界A:leaf 文件 over-report 危害随任务变(judge-independent)===")
print("  (fp=照抄假依赖方率;ob=误判'不安全'率;safe=判'安全'率)")
for proj in ["cpy", "wz"]:
    for task in ["T1", "T2"]:
        print(f"  [{proj} {task}]")
        for cond in ["correct", "over_strict", "over_humble"]:
            k = f"A_{proj}_{task}_{cond}"
            if k in report["A"]:
                r = report["A"][k]; print(f"     {cond:12s} fp={r['fp']:.2f}  over_block={r['ob']:.2f}  safe={r['safe']:.2f}")

print("\n=== 边界B:2×2 卡片长度×完整性,humble hedge 率(长度反射 vs 完整性检测)===")
print(f"  {'cell':10s} {'card_len':>8s} {'mode':>7s} {'hedge':>7s} {'DANGER':>7s} {'recall':>7s}")
order = ["shortC","shortI","longC","longI"]
for cell in order:
    for mode in ["humble","strict"]:
        k = f"B_{cell}_{mode}"
        if k in report["B"]:
            r = report["B"][k]; cl = manifest[k]["card_len"]
            print(f"  {cell:10s} {cl:8d} {mode:>7s} {r['hed']:7.2f} {r['dang']:7.2f} {r['rec']:7.2f}")
# 关键检验:humble hedge 短卡片(对 vs 缺) 和 长卡片(对 vs 缺)
def h(cell): return report["B"].get(f"B_{cell}_humble",{}).get("hed")
print("\n[关键对照 humble hedge]")
print(f"  短卡片: 对(shortC)={h('shortC')} vs 缺(shortI)={h('shortI')}  -> 差={round((h('shortI') or 0)-(h('shortC') or 0),3)}")
print(f"  长卡片: 对(longC)={h('longC')} vs 缺(longI)={h('longI')}  -> 差={round((h('longI') or 0)-(h('longC') or 0),3)}")
print(f"  完整性效应(缺-对,控长度后): 短 {round((h('shortI') or 0)-(h('shortC') or 0),3)}, 长 {round((h('longI') or 0)-(h('longC') or 0),3)}")
print(f"  长度效应(短-长,控完整性后): 对 {round((h('shortC') or 0)-(h('longC') or 0),3)}, 缺 {round((h('shortI') or 0)-(h('longI') or 0),3)}")
json.dump(report, open(D/"score_report.json","w",encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
print("\n写出", D/"score_report.json")
