"""M18 任务二:用 Python 标准库 ast 独立抽取 werkzeug 依赖边(与项目的 tree-sitter
repo_parser 完全解耦),用于构造去循环金标准 + 量化两解析器一致率。
红线:本脚本零 import repo_parser / chunking,只用 stdlib ast。
"""
import ast, os, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
WZ = ROOT / "repos" / "werkzeug"

# 收集所有 .py 的相对路径(相对 werkzeug 包根),建立"模块路径->文件"映射
files = []
for p in WZ.rglob("*.py"):
    rel = p.relative_to(WZ).as_posix()
    files.append(rel)
fileset = set(files)

def mod_to_file(parts):
    """模块点路径 parts(相对 werkzeug 根)-> 仓库内文件相对路径,解析不到返回 None。"""
    cand_mod = "/".join(parts) + ".py"
    cand_pkg = "/".join(parts) + "/__init__.py"
    if cand_mod in fileset: return cand_mod
    if cand_pkg in fileset: return cand_pkg
    return None

def resolve_relative(importer_rel, level, module):
    """解析 from (.*level) module import ... -> 目标文件相对路径。"""
    pkg_parts = importer_rel.split("/")[:-1]  # importer 所在包(去掉文件名)
    if importer_rel.endswith("__init__.py"):
        base = pkg_parts  # __init__ 自身就是包
    else:
        base = pkg_parts
    # level=1 当前包;level=2 上一层
    up = level - 1
    target_base = base[:len(base) - up] if up <= len(base) else []
    mod_parts = module.split(".") if module else []
    return mod_to_file(target_base + mod_parts)

# 正向 import 边(file -> 仓库内 files)+ 类继承(ast 独立)
fwd = {}   # importer_rel -> set(imported_rel)
bases = {} # (classname, file) -> list(base simple names)  via ast
classfile = {}  # classname -> file (简单名,可能冲突,够用)
for rel in files:
    src = (WZ / rel).read_text(encoding="utf-8", errors="replace")
    try: tree = ast.parse(src)
    except SyntaxError: continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            tgt = resolve_relative(rel, node.level or 0, node.module or "")
            if tgt and tgt != rel:
                fwd.setdefault(rel, set()).add(tgt)
        elif isinstance(node, ast.Import):
            for a in node.names:
                # 绝对 import werkzeug.X -> 去掉 werkzeug 前缀
                parts = a.name.split(".")
                if parts and parts[0] == "werkzeug":
                    tgt = mod_to_file(parts[1:])
                    if tgt and tgt != rel: fwd.setdefault(rel, set()).add(tgt)
        elif isinstance(node, ast.ClassDef):
            bn = []
            for b in node.bases:
                if isinstance(b, ast.Name): bn.append(b.id)
                elif isinstance(b, ast.Attribute): bn.append(b.attr)
            bases[(node.name, rel)] = bn
            classfile.setdefault(node.name, rel)

# 反向边
rev = {}
for importer, tgts in fwd.items():
    for t in tgts:
        rev.setdefault(t, set()).add(importer)

out = {
    "n_files": len(files),
    "forward": {k: sorted(v) for k, v in fwd.items()},
    "reverse": {k: sorted(v) for k, v in rev.items()},
    "bases": {f"{k[0]}@{k[1]}": v for k, v in bases.items()},
    "classfile": classfile,
}
(ROOT / "results" / "ast_edges_werkzeug.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"ast 独立抽取:{len(files)} 文件,正向边覆盖 {len(fwd)} 文件,反向边 {len(rev)} 文件,类 {len(bases)}")

# 与现有 tree-sitter 金标准交叉核对(量化一致率)——证明答案是否真实
cases = [json.loads(l) for l in open(ROOT/"data"/"testcases_werkzeug.jsonl", encoding="utf-8") if l.strip() and not l.startswith("//")]
def fwd_keywords_match(rel):
    # 现有 forward_dep 用例的 keyword_all = 被 import 的模块名(basename 去.py)
    return {Path(x).stem for x in fwd.get(rel, [])}
agree = tot = 0
detail = []
for c in cases:
    if c["category"] != "forward_dep": continue
    src = c.get("expected_sources", [None])[0]
    if not src: continue
    gold_kw = set(c["judge"].get("keywords", []))
    ast_kw = fwd_keywords_match(src)
    hit = len(gold_kw & ast_kw); tot_g = len(gold_kw)
    agree += hit; tot += tot_g
    detail.append((c["id"], src, sorted(gold_kw), sorted(ast_kw), f"{hit}/{tot_g}"))
print(f"\nforward_dep 金标准 keyword 与 ast 独立抽取的一致:{agree}/{tot} = {agree/tot:.1%}")
for d in detail[:6]: print("  ", d[0], d[1], "gold",d[2],"ast",d[3], d[4])
