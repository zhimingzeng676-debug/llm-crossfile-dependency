# -*- coding: utf-8 -*-
"""迁移任务(调用图)数据集构造:judge-independent gold = 用 repo_parser 的 import 解析
算出"函数 F 调用了哪些定义在其它文件的项目内函数"。小样本 demo(20-50 条)。
两条件:baseline(只给 F 源码)vs +card(给 F 源码 + 算好的跨文件调用结构卡片)。"""
import os, sys, json
sys.path.insert(0, r"D:/claude/49_交付/03_代码/src")
from repomind_lab.repo_parser import parse_repo

WZ = r"D:/claude/49/repos/werkzeug"
OUT = r"D:/claude/49_交付/07_泛化夯实"
g = parse_repo(WZ)

# 唯一定义文件的函数(避免重名歧义)
deffiles = {}
for f in g.functions:
    deffiles.setdefault(f.name, set()).add(f.file)
uniq = {n: next(iter(fs)) for n, fs in deffiles.items() if len(fs) == 1}

COMMON = {"type", "repr", "get", "set", "update", "items", "keys", "values", "copy",
          "pop", "add", "append", "name", "value", "len", "str", "int", "list", "dict"}

cand = []
for f in g.functions:
    if f.name.startswith("__") or len(f.name) < 4:
        continue
    file_a = f.file
    amap = g.aliases.get(file_a, {})
    gold = {}
    for n in f.calls:
        # 只认"被 import 进本文件的简单名"且解析到另一文件的项目函数(干净跨文件信号)
        if n not in amap or n in COMMON or len(n) < 4:
            continue
        rname, dfile = g.resolve_symbol(file_a, n)
        if dfile and dfile != file_a and rname in uniq:
            gold[rname] = dfile
    if 1 <= len(gold) <= 8:
        cand.append((f, gold))

# 平衡选样:多callee(≥2)优先,再补单callee;每文件≤4,目标 ~30
cand.sort(key=lambda x: -len(x[1]))
cases = []; seen_files = {}
for f, gold in cand:
    if seen_files.get(f.file, 0) >= 4:
        continue
    seen_files[f.file] = seen_files.get(f.file, 0) + 1
    cases.append((f, gold))
    if len(cases) >= 30:
        break
print(f"cases={len(cases)} | 覆盖文件数={len(set(c[0].file for c in cases))} | "
      f"≥2callee={sum(1 for _,g2 in cases if len(g2)>=2)} =1={sum(1 for _,g2 in cases if len(g2)==1)}")

def bundle(card):
    out = []
    for i, (f, gold) in enumerate(cases):
        q = (f"在 werkzeug 项目中,函数 `{f.name}`(定义于 {f.file})调用了哪些"
             f"【定义在其它文件】的项目内函数?只列出函数名,逐条列全。")
        ctx = f"[函数源码] {f.file} 中的 {f.name}:\n{f.code[:1800]}\n"
        if card:
            lines = "\n".join(f"  - {n}(定义于 {df})" for n, df in sorted(gold.items()))
            ctx += (f"\n[调用结构卡片 — 静态分析算出的跨文件调用目标]\n{lines}\n")
        gen_prompt = (f"你是代码调用关系分析助手。根据提供的信息准确回答问题,只列出函数名。\n\n{ctx}\n问题:{q}\n请直接回答。")
        out.append({"id": f"CG-{i:02d}", "caller": f.name, "file": f.file,
                    "question": q, "gold": ", ".join(sorted(gold.keys())),
                    "difficulty": "medium", "category": "callgraph", "gen_prompt": gen_prompt})
    return out

os.makedirs(OUT, exist_ok=True)
json.dump(bundle(False), open(os.path.join(OUT, "bundle_cg_baseline.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(bundle(True), open(os.path.join(OUT, "bundle_cg_card.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved bundle_cg_baseline.json / bundle_cg_card.json")
# 样例
f, gold = cases[0]
print("样例", f.name, "(", f.file, ") gold=", list(gold.keys()))
