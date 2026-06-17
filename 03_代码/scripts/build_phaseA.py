"""M17 Phase A:为独立裁判重判构建 bundle + 转换答案格式。
生成固定(已存 answers_*.json),只换裁判 → 完美隔离被污染的"裁判"变量。
产出到 results/phaseA/:bundle_werkzeug.json + ans_<cond>.json(runs格式)。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_judge_prompts import gold_points

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
OUT = R / "phaseA"; OUT.mkdir(exist_ok=True)

# 1) 读 56 testcases 的 notes/difficulty/category
cases = {}
for line in open(ROOT / "data" / "testcases_werkzeug.jsonl", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("//"): continue
    c = json.loads(line)
    cases[c["id"]] = c

# 2) bundle:question+gold 跨条件相同,取自 full_general 的 prompts
prompts = json.load(open(R / "prompts_werkzeug_full_general.json", encoding="utf-8"))
bundle = []
for p in prompts:
    cid = p["id"]; c = cases[cid]
    bundle.append({
        "id": cid,
        "question": p["question"],
        "gold": gold_points(p["judge"]),
        "notes": c.get("notes", ""),
        "difficulty": p.get("difficulty", c.get("difficulty", "?")),
        "category": p.get("category", c.get("category", "?")),
    })
json.dump(bundle, open(OUT / "bundle_werkzeug.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bmap = {b["id"]: b for b in bundle}
print(f"bundle_werkzeug.json: {len(bundle)} 条")

# 3) 转换答案:[{id,answer}] -> {runs:[[{id,difficulty,category,answer}]]}(单run)
CONDS = ["werkzeug_baseline_general", "werkzeug_full_general", "werkzeug_pe_system",
         "werkzeug_pe_cot", "werkzeug_pe_domain", "werkzeug_purellm_general",
         "werkzeug_graphcards_general"]
for cond in CONDS:
    f = R / f"answers_{cond}.json"
    if not f.exists(): print(f"  跳过(无答案):{cond}"); continue
    ans = json.load(open(f, encoding="utf-8"))
    run = []
    for a in ans:
        b = bmap.get(a["id"])
        if not b: continue
        run.append({"id": a["id"], "difficulty": b["difficulty"], "category": b["category"], "answer": a["answer"]})
    json.dump({"n_runs": 1, "runs": [run]}, open(OUT / f"ans_{cond}.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  ans_{cond}.json: {len(run)} 题")
print("Phase A 输入就绪 ->", OUT)
