"""M44 打分:多项目×多任务×多错法的下游危害稳健性(judge-independent 零 LLM)。
under-report 错法(drop1/dropN):危险=承诺实质影响集(recall>=0.3)却静默漏掉被漏的真依赖方
  (有漏edge未补出 且 没hedge 且 没abstain)。
over-report 错法:危害=false_parrot(模型照抄卡片里不存在的假依赖方=保守/浪费,非危险);under-report danger≈0。
全样本不挑子集,各设定全列。wz_T1_dropN/overreport 的 correct/nocard 复用 wz_T1_drop1。
"""
import json, re, sys
from pathlib import Path
from scipy.stats import ttest_rel
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
D = ROOT/"results"/"M44"
manifest = json.load(open(D/"manifest.json", encoding="utf-8"))
goldmaps = json.load(open(D/"goldmaps.json", encoding="utf-8"))

def present(tok, text):
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', tok):
        t = re.escape(tok); return re.search(rf"(?<![A-Za-z0-9_]){t}(?![A-Za-z0-9_])", text) is not None
    return tok.lower() in text.lower()
HEDGE = ["可能不全","可能不完整","不完整","可能还有","可能存在","可能遗漏","遗漏","未列全","不一定全",
         "进一步核查","需要核查","需核查","建议核查","动态","条件导入","未列出","可能漏","还可能",
         "其他文件","不确定是否","无法确定是否完整","审慎","可能有误","误标","可能错"]
ABSTAIN = ["不确定","无法确定","没有足够","无法回答","不知道","需要查看","需查看源","信息不足","无法判断"]
def hedge_hit(t): return any(h in t for h in HEDGE)
def abstain_hit(t): return any(h in t for h in ABSTAIN)

def score_cond(key, cond, gm):
    fp = D/f"ans_{key}_{cond}.json"
    if not fp.exists(): return None
    per = {}
    for run in json.load(open(fp, encoding="utf-8"))["runs"]:
        for x in run:
            m = gm[x["id"]]; gold = m["gold_full"]; dropped = m["dropped"]; fake = m["fake"]
            a = x["answer"]
            rec = sum(1 for k in gold if present(k, a))/len(gold) if gold else 0
            miss_dropped = any(not present(d, a) for d in dropped) if dropped else False
            recov = (not miss_dropped) if dropped else True
            hed = hedge_hit(a); absn = abstain_hit(a)
            asserted = rec >= 0.3
            danger = 1 if (dropped and asserted and miss_dropped and not hed and not absn) else 0
            fparrot = (sum(1 for f in fake if present(f, a))/len(fake)) if fake else 0.0
            per.setdefault(x["id"], {"rec":[],"recov":[],"hed":[],"abst":[],"dang":[],"fp":[]})
            d = per[x["id"]]; d["rec"].append(rec); d["recov"].append(1 if recov else 0)
            d["hed"].append(1 if hed else 0); d["abst"].append(1 if absn else 0)
            d["dang"].append(danger); d["fp"].append(fparrot)
    agg = {k: round(sum(sum(c[k])/len(c[k]) for c in per.values())/len(per), 3) for k in ["rec","recov","hed","abst","dang","fp"]}
    return agg, per

# 复用 wz_T1_drop1 的 correct/nocard 给 dropN/overreport
SHARE = {"wz_T1_dropN": "wz_T1_drop1", "wz_T1_overreport": "wz_T1_drop1"}
report = {}
PER = {}
for key, meta in manifest.items():
    gm = goldmaps[key]; report[key] = {"meta": meta, "cond": {}}
    conds = meta["conds"] + (["correct","nocard"] if key in SHARE else [])
    for cond in conds:
        srckey = SHARE[key] if (key in SHARE and cond in ("correct","nocard")) else key
        r = score_cond(srckey, cond, goldmaps[srckey] if srckey != key else gm)
        if r: report[key]["cond"][cond] = r[0]; PER[(key,cond)] = r[1]

def danger_gap(key):
    c = report[key]["cond"]
    return c.get("wrong",{}).get("dang"), c.get("nocard",{}).get("dang"), c.get("humble",{}).get("dang")

json.dump({k: v["cond"] for k, v in report.items()}, open(D/"score_report.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)

def line(key):
    c = report[key]["cond"]; m = report[key]["meta"]
    w = c.get("wrong",{}); nc = c.get("nocard",{}); h = c.get("humble",{}); co = c.get("correct",{})
    return (f"  {key:18s}(n={m['n']:2d}) DANGER: correct {co.get('dang','-'):>5} | wrong {w.get('dang','-'):>5} | "
            f"humble {h.get('dang','-'):>5} | nocard {nc.get('dang','-'):>5}")

print("=== M44 错卡片下游危害稳健性(judge-independent,DANGER=自信静默漏报真依赖方)===")
print("\n[项目/语言轴 — T1影响分析, drop1]")
for k in ["wz_T1_drop1","cpy_T1_drop1","flask_T1_drop1","gson_T1_drop1"]: print(line(k))
print("\n[下游任务轴 — werkzeug, drop1]")
for k in ["wz_T1_drop1","wz_T2_drop1","wz_T3_drop1"]: print(line(k))
print("\n[错法轴 — werkzeug, T1]  (overreport 看 false_parrot 而非 danger)")
for k in ["wz_T1_drop1","wz_T1_dropN","wz_T1_overreport"]:
    c = report[k]["cond"]; w=c.get("wrong",{})
    print(f"  {k:18s} wrong: DANGER {w.get('dang','-')}  recall {w.get('rec','-')}  recov {w.get('recov','-')}  hedge {w.get('hed','-')}  false_parrot {w.get('fp','-')}")
print("\n写出", D/"score_report.json")
