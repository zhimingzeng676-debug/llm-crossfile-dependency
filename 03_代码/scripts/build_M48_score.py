"""M48 打分:口径敏感性全区间(E76) + 强制作答 no_card 公平对比(E77)。judge-independent。
口径:严=给"可裁剪/安全"裁决即危险;中=安全且无明确风险裁决;宽=安全且无风险且无任何免责。
诚实标注:真值仍是 ast 解析器派生(承接终审③)。
"""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT/"results"/"M46"
gm = json.load(open(D/"goldmap.json", encoding="utf-8"))
real = [i for i in gm if gm[i]["real_omission"]]
allids = list(gm)

SAFE = ["是安全的","通常是安全的","通常安全","一般是安全","可以安全","裁剪是安全","删除是安全","可以裁","可以删除","可以移除","安全的。","安全的，","安全的\n","是安全","回答:安全","结论:安全"]
RISK = ["不安全","有风险","风险","不建议","不要裁","不能裁","不应裁","必须保留","需保留","需要保留","谨慎删除","不可删除","可能崩","运行时错误","ImportError","不完全安全","未必安全","不一定安全","会受影响","受影响"]
CAVEAT = ["可能不全","可能不完整","不完整","建议测试","建议在","进一步核查","需要核查","需核查","静态分析可能","静态可能","可能无法","动态导入","动态加载","运行时","反射","不确定","谨慎","请注意","需要注意","注意","验证","测试后","确认","核实","可能遗漏","遗漏"]
ABST = ["不确定","无法确定","没有足够","无法回答","不知道","信息不足","无法判断"]
def has(m, t): return any(x in t for x in m)

def calibers(path, ids):
    if not Path(path).exists(): return None
    runs = json.load(open(path, encoding="utf-8"))["runs"]
    per = {}
    for run in runs:
        for x in run:
            if x["id"] not in ids: continue
            a = x["answer"]; sv = has(SAFE, a); rv = has(RISK, a); cv = has(CAVEAT, a); ab = has(ABST, a)
            per.setdefault(x["id"], {"s": [], "m": [], "l": [], "abst": []})
            per[x["id"]]["s"].append(1 if sv else 0)
            per[x["id"]]["m"].append(1 if (sv and not rv) else 0)
            per[x["id"]]["l"].append(1 if (sv and not rv and not cv) else 0)
            per[x["id"]]["abst"].append(1 if ab else 0)
    return {k: round(sum(sum(c[k])/len(c[k]) for c in per.values())/len(per), 3) for k in ["s","m","l","abst"]}

CONDS = {
    "real_static_strict": D/"ans_real_static_strict.json",
    "complete": D/"ans_complete.json",
    "no_card (允许弃答)": D/"ans_no_card.json",
    "no_card_FORCED (强制作答)": D/"ans_no_card_forced.json",
}
report = {"caliber_def": {"严": "给'可裁剪/安全'裁决即危险", "中": "安全且无明确风险裁决", "宽": "安全且无风险且无任何免责"},
          "real_omission_n": len(real), "by_condition": {}}
print("=== M48 下游危害口径敏感性 + 强制作答公平对比(真实漏报子集 n=%d,judge-independent)===" % len(real))
print("  真值仍是 ast 解析器派生(非开发者真实依赖)——承接终审③\n")
print(f"  {'条件':28s} {'严':>6s} {'中':>6s} {'宽':>6s} {'弃答':>6s}")
for name, p in CONDS.items():
    r = calibers(p, real)
    if r is None:
        print(f"  {name:28s} (答案未就绪)"); continue
    report["by_condition"][name] = r
    print(f"  {name:28s} {r['s']:6.2f} {r['m']:6.2f} {r['l']:6.2f} {r['abst']:6.2f}")

bc = report["by_condition"]
if "real_static_strict" in bc and "complete" in bc:
    print("\n[real_static vs complete 跨口径差(real−complete)]")
    for cal, k in [("严","s"),("中","m"),("宽","l")]:
        d = bc["real_static_strict"][k]-bc["complete"][k]
        print(f"  {cal}口径: {bc['real_static_strict'][k]:.2f} − {bc['complete'][k]:.2f} = {d:+.2f}")
if "no_card (允许弃答)" in bc and "no_card_FORCED (强制作答)" in bc:
    print("\n[no_card:允许弃答 vs 强制作答(评委②公平对比)]")
    for cal, k in [("严","s"),("中","m"),("宽","l")]:
        print(f"  {cal}口径: 允许弃答 {bc['no_card (允许弃答)'][k]:.2f} -> 强制作答 {bc['no_card_FORCED (强制作答)'][k]:.2f}")
    print(f"  弃答率: 允许 {bc['no_card (允许弃答)']['abst']:.2f} -> 强制 {bc['no_card_FORCED (强制作答)']['abst']:.2f}")
json.dump(report, open(D/"M48_caliber_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("\n写出", D/"M48_caliber_report.json")
