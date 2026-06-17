"""M36-37 任务一(2):脏依赖识别的 judge-independent 确定性复算(加固版)。
对 strict/humble/baseline 三种 prompt 的脏用例答案(每种 10 runs),
用确定性关键词指标(零 LLM)判定模型是否"正确识别脏依赖的脏性质":
  - dynamic 用例:答案须点出"运行时/动态决定/无法静态确定"机制(>=1 命中);
  - conditional 用例:答案须点出"条件/可选/try-except/缺失降级"性质(>=1 命中)。
加固=双指标:I1 机制标记命中;I2 同时点出具体机制词(__import__/importlib/try/except)。
覆盖 d3(中性措辞,排除问题措辞与 humble 对齐混淆) 与 d2(原措辞) 两套。
"""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
R = ROOT/"results"/"dirty"; OUT = ROOT/"results"/"judge_independent"; OUT.mkdir(parents=True, exist_ok=True)

# 确定性标记(judge-independent)。I1=性质标记;I2=具体机制词。
DYN_I1 = ["动态", "运行时", "无法静态", "不能静态", "静态无法", "无法确定", "不能确定",
          "取决于", "随数据", "随运行时", "运行时数据", "运行时输入", "运行时确定", "运行时决定", "被反序列化"]
DYN_I2 = ["__import__", "importlib", "import_module", "getattr", "反射"]
CON_I1 = ["条件", "可选", "缺失", "降级", "回退", "备选", "optional", "并非", "不一定", "若安装", "如果安装", "未安装"]
CON_I2 = ["try", "except", "ImportError", "try/except", "try-except"]

def hit(markers, text):
    return any(m.lower() in text.lower() for m in markers)

def correct_flag(cat, text):
    """返回 (I1命中, I1&I2命中)。"""
    if cat == "dynamic":
        i1 = hit(DYN_I1, text) or hit(DYN_I2, text)
        i2 = i1 and hit(DYN_I2, text)
        return i1, i2
    if cat == "reflection":
        i1 = hit(["反射", "getattr", "运行时", "动态", "无法静态", "字符串", "属性名"], text)
        i2 = i1 and ("getattr" in text or "反射" in text)
        return i1, i2
    if cat == "conditional":
        i1 = hit(CON_I1, text)
        i2 = i1 and hit(CON_I2, text)
        return i1, i2
    return False, False

def score_set(bundle_fn, ans_files):
    bundle = json.load(open(R/bundle_fn, encoding="utf-8"))
    cat = {b["id"]: b["category"] for b in bundle}
    res = {}
    for label, fn in ans_files.items():
        a = json.load(open(R/fn, encoding="utf-8"))
        runs = a["runs"]; nrun = len(runs)
        # 每个用例:在 10 runs 上的命中率;再对用例取平均 -> 整体识别率
        per_case_i1, per_case_i2 = {}, {}
        for run in runs:
            for x in run:
                cid = x["id"]; c = cat.get(cid)
                i1, i2 = correct_flag(c, x["answer"])
                per_case_i1.setdefault(cid, []).append(1 if i1 else 0)
                per_case_i2.setdefault(cid, []).append(1 if i2 else 0)
        ids = list(per_case_i1)
        macro_i1 = sum(sum(v)/len(v) for v in per_case_i1.values())/len(ids)
        macro_i2 = sum(sum(v)/len(v) for v in per_case_i2.values())/len(ids)
        # 分类别
        bycat = {}
        for c in set(cat.values()):
            cids = [i for i in ids if cat[i] == c]
            if not cids: continue
            bycat[c] = {
                "n": len(cids),
                "I1": round(sum(sum(per_case_i1[i])/len(per_case_i1[i]) for i in cids)/len(cids), 3),
                "I2": round(sum(sum(per_case_i2[i])/len(per_case_i2[i]) for i in cids)/len(cids), 3),
            }
        res[label] = {"n_cases": len(ids), "n_runs": nrun,
                      "identify_I1": round(macro_i1, 3), "identify_I2_hard": round(macro_i2, 3),
                      "by_category": bycat}
    return res

report = {}
report["d3_neutral"] = score_set("bundle_d3_strict.json", {
    "strict": "ans_d3_strict.json", "humble": "ans_d3_humble.json", "baseline": "ans_d3_baseline.json"})
# d2 原措辞(若答案文件存在)
d2ans = {}
for label, fn in {"strict": "ans_d2_strict.json", "humble": "ans_d2_humble.json", "baseline": "ans_d2_baseline.json"}.items():
    if (R/fn).exists(): d2ans[label] = fn
if d2ans:
    report["d2_original"] = score_set("bundle_d2_strict.json", d2ans)

json.dump(report, open(OUT/"dirty_objective.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("=== 脏依赖识别 judge-independent 确定性复算(零 LLM) ===")
for setname, r in report.items():
    print(f"\n[{setname}]")
    for label, s in r.items():
        print(f"  {label:9s} n={s['n_cases']}x{s['n_runs']}runs  "
              f"识别率 I1={s['identify_I1']:.0%}  双指标I2(加固)={s['identify_I2_hard']:.0%}")
        for c, cc in s["by_category"].items():
            print(f"       - {c:12s} n={cc['n']}  I1={cc['I1']:.0%}  I2={cc['I2']:.0%}")
print("\n写出:", OUT/"dirty_objective.json")
