# -*- coding: utf-8 -*-
"""verify_07.py — 07_泛化夯实(前沿大模型验证 + 调用图迁移)的无 GPU / 无 API 一键复现。
从仓库内归档的逐实例预测 + gold 现算判分无关 det gold-recall;LLM-judge 均值直接读归档。
运行:python verify_07.py   (在 07_泛化夯实/ 目录下,或从仓库根 `python 07_泛化夯实/verify_07.py`)
"""
import os, json
HERE = os.path.dirname(os.path.abspath(__file__))
def J(name): return json.load(open(os.path.join(HERE, name), encoding="utf-8"))

def det_recall(ans_file, gold):
    run = J(ans_file)["runs"][0]
    num = den = 0.0
    for r in run:
        kw = gold.get(r["id"], []); t = (r["answer"] or "").lower()
        if not kw: continue
        num += sum(1 for k in kw if k in t) / len(kw); den += 1
    return round(num / den, 4) if den else None

print("=" * 64)
print("verify_07.py — 强模型验证 + 调用图迁移,判分无关复现(无 GPU/API)")
print("=" * 64)

# ---------------- 任务一:前沿大模型验主线 ----------------
print("\n# 强模型验证(werkzeug 56,det gold-recall + 归档 LLM-judge)")
gold = {b["id"]: [x.strip().lower() for x in b["gold"].split(",") if x.strip()]
        for b in J("sm_bundle_werkzeug_baseline_general.json")}
def jm(f):
    p = os.path.join(HERE, f)
    return round(json.load(open(p, encoding="utf-8"))["mean"], 4) if os.path.exists(p) else None
print(f"  {'模型':16}{'baseline d/j':>16}{'full d/j':>16}{'pecot d/j':>16}{'RAG杠杆':>9}{'PE增量':>9}")
ref = {"baseline": (0.287, 0.18), "full": (0.885, 0.96), "pecot": (0.940, 0.96)}
for tag, name in [("deepseek", "deepseek-v4-pro"), ("qwen3", "qwen3-235b")]:
    d = {c: det_recall(f"sm_ans_{tag}_{c}.json", gold) for c in ["baseline", "full", "pecot"]}
    j = {c: jm(f"sm_judge_{tag}_{c}.json") for c in ["baseline", "full", "pecot"]}
    lev = f"{d['full']/d['baseline']:.1f}x" if d["baseline"] else "?"
    pe = f"{d['pecot']-d['full']:+.3f}"
    print(f"  {name:16}{d['baseline']:.3f}/{j['baseline']:.2f}    {d['full']:.3f}/{j['full']:.2f}    {d['pecot']:.3f}/{j['pecot']:.2f}    {lev:>9}{pe:>9}")
print(f"  {'Qwen2.5-14B(对照)':16}{ref['baseline'][0]:.3f}/{ref['baseline'][1]:.2f}    {ref['full'][0]:.3f}/{ref['full'][1]:.2f}    {ref['pecot'][0]:.3f}/{ref['pecot'][1]:.2f}    {'3.1x':>9}{'+0.055':>9}")
print("  => 前沿 baseline 不高于 14B(连 ~17× 大的 qwen3 也列不出依赖)→ 容量受限被证伪;RAG 杠杆更大;PE 仍边际。")

# ---------------- 任务二:调用图迁移 ----------------
print("\n# 调用图迁移(n=30,det gold-recall,judge-independent)")
cg_gold = {b["id"]: [x.strip().lower() for x in b["gold"].split(",") if x.strip()]
           for b in J("bundle_cg_baseline.json")}
b = det_recall("ans_cg_baseline.json", cg_gold); c = det_recall("ans_cg_card.json", cg_gold)
print(f"  baseline(只给函数源码) = {b:.3f}")
print(f"  +结构卡片(喂算好的跨文件调用)= {c:.3f}   (提升 +{c-b:.3f})")
print("  => 喂结构方向迁移(到满分);但 baseline 已高(0.82)因调用名在源码里可见——价值在'结构最难从局部看出处'最大。")
print("\n[verify_07] done. 两块均无需 GPU/API,clone 即复现。")
