"""生成 werkzeug 跨文件依赖分析评测集(≥50 条,标准答案由静态依赖图导出)。

设计哲学:**实体选择 + 难度 + 问法由人策划,标准答案由 tree-sitter 依赖图程序化
计算** —— 这样答案"基于真实代码、可追溯文件、可人工核验",又不靠人脑记忆易错。
难度按依赖扇出/跳数自动定档,judge 用 keyword 部分给分(沿用判定审计标准)。

用法:python scripts/build_werkzeug_dataset.py
输出:data/testcases_werkzeug.jsonl + 终端打印类型/难度分布。
"""

import collections
import json

from _common import PROJECT_ROOT

from repomind_lab.repo_parser import parse_repo

REPO = "repos/werkzeug"
OUT = PROJECT_ROOT / "data" / "testcases_werkzeug.jsonl"


def main():
    g = parse_repo(PROJECT_ROOT / REPO)
    edges = g.import_edges()
    deps_of = collections.defaultdict(set)      # 文件 -> 依赖的仓库内文件
    importers_of = collections.defaultdict(set)  # 文件 -> import 它的文件
    for a, b in edges:
        deps_of[a].add(b)
        importers_of[b].add(a)
    cls_file = {c.name: c.file for c in g.classes}
    cls_bases = {c.name: c.bases for c in g.classes}
    subclasses = collections.defaultdict(list)
    for sub, base in g.class_edges():
        subclasses[base].append(sub)

    def transitive_deps(start, max_depth=4):
        """BFS 求传递依赖,返回 {文件: 最短跳数}。"""
        seen = {start: 0}
        frontier = [start]
        for d in range(1, max_depth + 1):
            nxt = []
            for x in frontier:
                for y in deps_of.get(x, ()):
                    if y not in seen:
                        seen[y] = d
                        nxt.append(y)
            frontier = nxt
        return seen

    def stem(path):
        """文件路径 -> 判定关键词形式。普通文件取去扩展名的文件名(structures.py->structures);
        包 __init__.py 取包名(datastructures/__init__.py->datastructures)。
        这是相对导入(from .structures)、图卡片、答案叙述里都会出现的形式 ——
        用全路径当关键词不公平(原始代码是相对导入,拼不出全路径),会污染瓶颈诊断。"""
        if path.endswith("/__init__.py"):
            return path.rsplit("/", 2)[-2]
        return path.rsplit("/", 1)[-1][:-3] if path.endswith(".py") else path

    def stems(paths):
        seen = []
        for p in paths:
            s = stem(p)
            if s not in seen:
                seen.append(s)
        return seen

    cases = []

    def add(cid, category, difficulty, question, keywords, expected, notes, judge_type="keyword_all"):
        cases.append({
            "id": cid, "category": category, "difficulty": difficulty,
            "priority": "P1", "question": question,
            "judge": {"type": judge_type, "keywords": keywords},
            "expected_sources": expected, "notes": notes,
        })

    # ---------- A. 正向依赖:某文件 import 了哪些仓库内模块 ----------
    fwd = ["wrappers/request.py", "routing/map.py", "wrappers/response.py",
           "sansio/request.py", "formparser.py", "test.py", "serving.py", "http.py",
           "routing/matcher.py", "sansio/response.py", "datastructures/headers.py"]
    for i, f in enumerate(sorted(fwd), 1):
        deps = sorted(deps_of.get(f, set()))
        if not deps:
            continue
        diff = "easy" if len(deps) <= 2 else ("medium" if len(deps) <= 5 else "hard")
        add(f"FWD-{i:02d}", "forward_dep", diff,
            f"在 werkzeug 中,{f} 这个文件直接依赖(import)了哪些项目内的模块?请列出文件。",
            stems(deps), [f],
            f"正向依赖,共 {len(deps)} 个:{deps}(来源:{f} 顶部 import 段)")

    # ---------- B. 反向依赖:哪些文件 import 了某模块(高扇入=hard) ----------
    rev = ["http.py", "exceptions.py", "datastructures/__init__.py", "wrappers/request.py",
           "wsgi.py", "utils.py", "sansio/request.py", "routing/rules.py",
           "datastructures/structures.py", "_internal.py", "urls.py", "formparser.py",
           "datastructures/mixins.py"]
    for i, m in enumerate(sorted(rev), 1):
        users = sorted(importers_of.get(m, set()))
        if not users:
            continue
        diff = "easy" if len(users) <= 2 else ("medium" if len(users) <= 6 else "hard")
        add(f"REV-{i:02d}", "reverse_dep", diff,
            f"在 werkzeug 中,哪些文件 import(依赖)了 {m}?请尽可能完整列出。",
            stems(users), [m],
            f"反向依赖,共 {len(users)} 个使用方:{users}。高扇入考察长上下文/跨文件关联")

    # ---------- C. 跨文件继承:类继承自谁 / 谁继承了它 ----------
    # C1 直接跨文件继承(基类在别的文件,基类名直接可解析)
    inh = ["Accept", "FileMultiDict", "EnvironHeaders", "RequestCacheControl",
           "ContentSecurityPolicy", "CombinedMultiDict"]
    for i, sub in enumerate(inh, 1):
        if sub not in cls_file:
            continue
        bases = [b for b in cls_bases.get(sub, []) if b in cls_file and cls_file[b] != cls_file[sub]]
        if not bases:
            continue
        base = bases[0]
        add(f"INH-{i:02d}", "inheritance", "medium",
            f"在 werkzeug 中,类 {sub} 继承自哪个类?那个基类定义在哪个文件?",
            [base, cls_file[base]], [cls_file[sub], cls_file[base]],
            f"{sub}({cls_file[sub]}) 继承自 {base}({cls_file[base]}),跨文件继承")

    # C2 别名跨文件继承(hard:基类经 `as` 改名,静态名字不匹配)
    add("INH-07", "inheritance", "hard",
        "在 werkzeug 中,wrappers/request.py 里的 Request 类继承自哪个文件里的哪个类?",
        ["sansio/request.py"], ["wrappers/request.py", "sansio/request.py"],
        "别名继承陷阱:base 写作 _SansIORequest,实为 `from ..sansio.request import Request as _SansIORequest`。"
        "名字不匹配,检索/解析易断裂——隐式依赖典型")
    add("INH-08", "inheritance", "hard",
        "在 werkzeug 中,wrappers/response.py 里的 Response 类的基类定义在哪个文件?",
        ["sansio/response.py"], ["wrappers/response.py", "sansio/response.py"],
        "同 INH-07:Response 继承自 sansio/response.py 的 Response(别名 _SansIOResponse)")
    # C3 多继承(hard)
    if "BadRequestKeyError" in cls_bases:
        add("INH-09", "inheritance", "hard",
            "在 werkzeug 中,异常类 BadRequestKeyError 同时继承了哪两个类?",
            cls_bases["BadRequestKeyError"], ["exceptions.py"],
            f"多继承:{cls_bases['BadRequestKeyError']}(exceptions.py)")
    # C4 子类枚举(谁继承了 HTTPException)hard
    http_subs = sorted(subclasses.get("HTTPException", []))
    if http_subs:
        diff = "hard" if len(http_subs) > 6 else "medium"
        add("INH-10", "inheritance", diff,
            "在 werkzeug 中,有哪些异常类直接继承自 HTTPException?请尽量列出。",
            http_subs, ["exceptions.py"],
            f"子类枚举,共 {len(http_subs)} 个直接子类(均在 exceptions.py)", judge_type="keyword_all")
    # C5 反向:某基类被谁继承(中等)
    for i, base in enumerate(["ImmutableDictMixin", "CallbackDict"], 11):
        kids = sorted(subclasses.get(base, []))
        if not kids:
            continue
        add(f"INH-{i}", "inheritance", "medium",
            f"在 werkzeug 中,哪些类继承(混入)了 {base}?",
            kids, [cls_file.get(base, "datastructures/mixins.py")],
            f"反向继承:{base} 被 {kids} 继承")

    # ---------- D. 类/符号定位:某类定义在哪个文件 ----------
    locs = ["Map", "Rule", "MapAdapter", "MultiDict", "Headers", "FileStorage",
            "HTTPException", "Authorization", "WSGIWarning", "BaseConverter",
            "StateMachineMatcher", "CombinedMultiDict"]
    for i, name in enumerate(sorted(set(locs)), 1):
        if name not in cls_file:
            continue
        add(f"LOC-{i:02d}", "symbol_location", "easy",
            f"在 werkzeug 中,类 {name} 定义在哪个文件里?",
            [cls_file[name]], [cls_file[name]],
            f"{name} 定义于 {cls_file[name]}")

    # ---------- E. 数据流/常量定位 ----------
    # 选有意义的模块级常量(过滤单字母 TypeVar)
    real_consts = [c for c in g.constants if len(c.name) > 2 and not c.name.isupper() or
                   (c.name.isupper() and len(c.name) > 2)]
    picked = []
    for c in real_consts:
        if c.name in {"PIN_TIME", "HELP_HTML", "OBJECT_DUMP_HTML"} and c.name not in [p.name for p in picked]:
            picked.append(c)
    for i, c in enumerate(picked, 1):
        add(f"DAT-{i:02d}", "dataflow", "easy",
            f"在 werkzeug 中,常量 {c.name} 在哪个文件中定义?",
            [c.file], [c.file],
            f"{c.name} @ {c.file}:{c.line}")

    # ---------- F. 传递/间接依赖(hard,多跳)----------
    chains = [
        ("wrappers/response.py", "datastructures/mixins.py"),
        ("routing/map.py", "datastructures/structures.py"),
        ("wrappers/request.py", "datastructures/structures.py"),
        ("routing/map.py", "http.py"),
    ]
    ci = 1
    for start, target in chains:
        td = transitive_deps(start)
        if target in td and td[target] >= 2:
            # 找一条 start -> mid -> ... -> target 的中间节点
            mids = [f for f, d in td.items() if d == 1 and target in transitive_deps(f, 2)]
            mid = sorted(mids)[0] if mids else None
            if mid:
                # 中间节点要求精确到全路径(如 datastructures/__init__.py):
                # 仅用 stem "datastructures" 会被问题/上下文里的同名 token 泄漏,
                # 而"精确指出哪个中间文件"正是间接依赖的考点,故用全路径。
                add(f"IND-{ci:02d}", "indirect_dep", "hard",
                    f"在 werkzeug 中,{start} 是否(间接)依赖 {target}?如果是,依赖路径恰好经过哪个中间文件(给出完整路径)?",
                    [mid], [start, mid],
                    f"间接依赖:{start} -> {mid} -> ... -> {target}(最短 {td[target]} 跳)。"
                    f"考察隐式/多跳依赖,单次检索拿不到中间节点")
                ci += 1
    # F2 "直接还是间接"判别(hard)
    add(f"IND-{ci:02d}", "indirect_dep", "hard",
        "在 werkzeug 中,wrappers/response.py 是直接 import 了 datastructures/structures.py,"
        "还是通过 datastructures/__init__.py 间接依赖的?给出完整的中间文件路径。",
        ["datastructures/__init__.py"], ["wrappers/response.py", "datastructures/__init__.py"],
        "response.py 直接依赖 datastructures/__init__.py(包),structures.py 是经由包再分发的间接依赖")

    # ---------- 落盘 ----------
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("// werkzeug 3.1.8 跨文件依赖分析评测集(自动生成,答案由静态依赖图导出)\n")
        fh.write("// 生成器:scripts/build_werkzeug_dataset.py。难度按依赖扇出/跳数自动定档。\n")
        for c in cases:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    by_cat = collections.Counter(c["category"] for c in cases)
    by_diff = collections.Counter(c["difficulty"] for c in cases)
    print(f"共生成 {len(cases)} 条用例 -> {OUT}")
    print("按类型:", dict(by_cat))
    print("按难度:", dict(by_diff))


if __name__ == "__main__":
    main()
