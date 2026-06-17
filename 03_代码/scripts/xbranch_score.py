# -*- coding: utf-8 -*-
"""支线复现打分(judge-independent)。humble: detect 关键词识破率;xlang: det gold-recall。"""
import json, os
X = "<REMOTE_WORKDIR>/xbranch"; D = "<REMOTE_WORKDIR>/phaseD"; M = "<REMOTE_WORKDIR>/phaseM"

# ---- 任务一:humble 识破率(模型答案是否点出"脏/动态/条件/可能不全")----
DIRTY = ["运行时", "运行期", "动态", "无法静态", "静态分析", "可能不完整", "可能遗漏", "未必", "条件",
         "可选", "反射", "__import__", "importlib", "try", "except", "缺失", "降级", "不确定",
         "插件", "entry_point", "getattr", "dynamic", "conditional", "reflection", "optional", "lazy"]
def detect_rate(f):
    run = json.load(open(f, encoding="utf-8"))["runs"][0]
    hit = sum(1 for r in run if any(k in (r["answer"] or "") for k in DIRTY))
    return hit / len(run), len(run)

print("=== 任务一:humble 脏依赖识破(judge-independent detect,N=103)===")
res1 = {}
for tag in ["strict", "humble"]:
    f = os.path.join(X, f"ans_{tag}.json")
    if os.path.exists(f):
        r, n = detect_rate(f); res1[tag] = round(r, 4)
        print(f"  {tag:8} detect率 = {r:.3f}  (N={n})")
if "strict" in res1 and "humble" in res1:
    print(f"  -> strict {res1['strict']:.2f} → humble {res1['humble']:.2f}  (宣称 0.07→0.99)")

# ---- 任务二:跨语言 det gold-recall(baseline vs full)----
def detrec(ansfile, bundle):
    gold = {b["id"]: [g.strip().lower() for g in b["gold"].split(",") if g.strip()]
            for b in json.load(open(bundle, encoding="utf-8"))}
    run = json.load(open(ansfile, encoding="utf-8"))["runs"][0]
    num = den = 0.0
    for r in run:
        kws = gold.get(r["id"], []); t = (r["answer"] or "").lower()
        if not kws: continue
        # gold token 或其 basename 命中
        hit = sum(1 for k in kws if k in t or os.path.basename(k) in t) / len(kws)
        num += hit; den += 1
    return num / den if den else 0.0, int(den)

print("\n=== 任务二:跨语言 Go/Java/C(judge-independent det gold-recall)===")
res2 = {}
for L, nm in [("go", "Go(gin)"), ("java", "Java(gson)"), ("c", "C(lua)")]:
    bb = os.path.join(D, f"bundle_{L}_baseline.json"); bf = os.path.join(D, f"bundle_{L}_full.json")
    ab = os.path.join(X, f"ans_{L}_baseline.json"); af = os.path.join(X, f"ans_{L}_full.json")
    if all(os.path.exists(p) for p in [ab, af, bb, bf]):
        rb, n = detrec(ab, bb); rf, _ = detrec(af, bf)
        res2[L] = dict(baseline=round(rb, 4), full=round(rf, 4), lift=round(rf - rb, 4), n=n)
        print(f"  {nm:11} baseline={rb:.3f} → full={rf:.3f}  提升 +{rf-rb:.3f}  (n={n})")
print("  (宣称:强裁判口径 +0.60~0.93;此处为 judge-independent det gold-recall,看方向是否同为大提升)")

json.dump({"humble": res1, "xlang": res2}, open(os.path.join(X, "xbranch_scores.json"), "w"), ensure_ascii=False, indent=1)
print("\nSAVED xbranch_scores.json | DONE")
