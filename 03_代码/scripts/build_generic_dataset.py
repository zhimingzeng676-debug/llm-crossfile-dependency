"""通用跨文件依赖用例生成器(M6 第二项目泛化验证用)。
对任意仓库自动按扇入/扇出/继承挑实体,生成 ~25 条用例(答案由依赖图导出)。

用法:python scripts/build_generic_dataset.py repos/rich data/testcases_rich.jsonl
"""

import collections
import json
import sys

from _common import PROJECT_ROOT
from repomind_lab.repo_parser import parse_repo


def stem(p):
    if p.endswith("/__init__.py"):
        return p.rsplit("/", 2)[-2]
    return p.rsplit("/", 1)[-1][:-3] if p.endswith(".py") else p


def main():
    repo = sys.argv[1]
    out = sys.argv[2]
    g = parse_repo(PROJECT_ROOT / repo)
    edges = g.import_edges()
    deps_of, importers_of = collections.defaultdict(set), collections.defaultdict(set)
    for a, b in edges:
        deps_of[a].add(b); importers_of[b].add(a)
    cls_set = {(c.name, c.file) for c in g.classes}

    fan_in = collections.Counter(b for a, b in edges)
    fan_out = collections.Counter(a for a, b in edges)
    cases = []

    def add(cid, cat, diff, q, kws, exp, jt="keyword_all"):
        cases.append({"id": cid, "category": cat, "difficulty": diff, "priority": "P1",
                      "question": q, "judge": {"type": jt, "keywords": kws},
                      "expected_sources": exp, "notes": f"{cat}: {kws}"})

    # reverse_dep:扇入最高的 6 个(hard)
    for i, (m, n) in enumerate(fan_in.most_common(6), 1):
        users = sorted(importers_of[m])
        diff = "hard" if n > 5 else "medium"
        add(f"R-REV-{i:02d}", "reverse_dep", diff,
            f"在该项目中,哪些文件 import(依赖)了 {m}?请尽量列全。", stems_uniq(users), [m])
    # forward_dep:扇出最高的 5 个
    for i, (f, n) in enumerate(fan_out.most_common(5), 1):
        deps = sorted(deps_of[f])
        diff = "hard" if n > 5 else "medium"
        add(f"R-FWD-{i:02d}", "forward_dep", diff,
            f"在该项目中,{f} 直接依赖(import)了哪些项目内模块?请列全。", stems_uniq(deps), [f])
    # inheritance:跨文件继承的 6 个(medium)
    cls_file = {c.name: c.file for c in g.classes}
    inh = 0
    for c in g.classes:
        bases = [b for b in c.bases if (rn_rf := g.resolve_symbol(c.file, b)) and rn_rf[1]
                 and (rn_rf[0], rn_rf[1]) in cls_set and rn_rf[1] != c.file]
        if not bases:
            continue
        rn, rf = g.resolve_symbol(c.file, bases[0])
        inh += 1
        add(f"R-INH-{inh:02d}", "inheritance", "medium",
            f"在该项目中,类 {c.name} 继承自哪个文件里的哪个类?", [rn, rf], [c.file, rf])
        if inh >= 6:
            break
    # symbol_location:6 个类(easy)
    import random
    random.seed(7)
    for i, c in enumerate(random.sample(g.classes, min(6, len(g.classes))), 1):
        add(f"R-LOC-{i:02d}", "symbol_location", "easy",
            f"在该项目中,类 {c.name} 定义在哪个文件里?", [c.file], [c.file])
    # indirect_dep:3 条多跳(hard)
    ind = 0
    for a in sorted(deps_of):
        for b in sorted(deps_of[a]):
            hit = [c for c in deps_of.get(b, set()) if c != a and c not in deps_of[a]]
            if hit:
                ind += 1
                add(f"R-IND-{ind:02d}", "indirect_dep", "hard",
                    f"在该项目中,{a} 是否间接依赖 {hit[0]}?经过哪个中间文件(完整路径)?", [b], [a, b])
                break
        if ind >= 3:
            break

    op = PROJECT_ROOT / out
    with open(op, "w", encoding="utf-8") as fh:
        fh.write(f"// {repo} 跨文件依赖泛化验证集(自动生成,答案由依赖图导出)\n")
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    by = collections.Counter(c["category"] for c in cases)
    print(f"{repo}: {len(cases)} 条 -> {out}  类型 {dict(by)}")


def stems_uniq(paths):
    seen = []
    for p in paths:
        s = stem(p)
        if s not in seen:
            seen.append(s)
    return seen


if __name__ == "__main__":
    main()
