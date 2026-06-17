"""M8 审计一:为 werkzeug 多生成间接依赖用例(补到 ≥15,验证 CoT/FT 结论是否稳健)。
答案由依赖图 BFS 导出,与已有 5 条 IND 尽量不重复。输出独立文件供专项重跑。
"""

import collections
import json

from _common import PROJECT_ROOT
from repomind_lab.repo_parser import parse_repo

# 已有 5 条 IND 用过的 (start,target),避免重复
USED = {("wrappers/request.py", "datastructures/structures.py"),
        ("routing/map.py", "datastructures/structures.py"),
        ("routing/map.py", "http.py"),
        ("wrappers/response.py", "datastructures/structures.py")}


def main():
    g = parse_repo(PROJECT_ROOT / "repos/werkzeug")
    deps = collections.defaultdict(set)
    for a, b in g.import_edges():
        deps[a].add(b)

    cases = []
    seen = set(USED)
    for a in sorted(deps):
        for b in sorted(deps[a]):
            for c in sorted(deps.get(b, set())):
                if c != a and c not in deps[a] and (a, c) not in seen:
                    seen.add((a, c))
                    i = len(cases) + 1
                    cases.append({
                        "id": f"XIND-{i:02d}", "category": "indirect_dep", "difficulty": "hard",
                        "priority": "P1",
                        "question": f"在 werkzeug 中,{a} 是否间接依赖 {c}?如果是,依赖路径恰好经过哪个中间文件(给出完整路径)?",
                        "judge": {"type": "keyword_all", "keywords": [b]},
                        "expected_sources": [a, b],
                        "notes": f"间接依赖:{a} -> {b} -> ... -> {c}。中间文件 {b}。"})
                    break  # 同一 a 每个 b 只取一条
            if sum(1 for x in cases if x["id"].startswith("XIND")) >= 18:
                break
        if len(cases) >= 18:
            break

    out = PROJECT_ROOT / "data" / "testcases_werkzeug_indirect.jsonl"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("// werkzeug 间接依赖扩充集(M8 审计一,补样本量)\n")
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"生成 {len(cases)} 条间接依赖用例 -> {out}")


if __name__ == "__main__":
    main()
