"""M18:用 ast 独立边(零 tree-sitter)为现有问题重建金标准 → 去循环金标准 bundle。
归一化:X/__init__.py 边按包名 X 标注(人类自然答案)。产出 independent_gold_bundle.json
+ 与 tree-sitter 金标准的一致率(差异逐条列出供人工核验)。
"""
import ast, json, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
E = json.load(open(ROOT/"results"/"ast_edges_werkzeug.json", encoding="utf-8"))
fwd, rev, bases, classfile = E["forward"], E["reverse"], E["bases"], E["classfile"]

def norm(rel):
    """文件相对路径 -> 人类标注名:X/__init__.py->包名X;否则 stem。"""
    if rel.endswith("/__init__.py"): return rel.split("/")[-2]
    return Path(rel).stem

cases = [json.loads(l) for l in open(ROOT/"data"/"testcases_werkzeug.jsonl", encoding="utf-8") if l.strip() and not l.startswith("//")]

# 函数定义位置(ast 独立):扫描所有文件的 def
funcfile = {}
WZ = ROOT/"repos"/"werkzeug"
for p in WZ.rglob("*.py"):
    rel = p.relative_to(WZ).as_posix()
    try: tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError: continue
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcfile.setdefault(n.name, rel)

def base_of(clsname):
    # 找该类的 ast 基类(可能多文件同名,取第一个有基类的)
    for k, v in bases.items():
        nm, f = k.rsplit("@", 1)
        if nm == clsname and v: return v, f
    for k, v in bases.items():
        nm, f = k.rsplit("@", 1)
        if nm == clsname: return v, f
    return None, None

out, agree_n, tot_n, diffs = [], 0, 0, []
for c in cases:
    cat, cid = c["category"], c["id"]
    src = (c.get("expected_sources") or [None])[0]
    gold_ts = set(c["judge"].get("keywords", []))
    ind = None  # 独立 gold keywords
    if cat == "forward_dep" and src in fwd:
        ind = sorted({norm(x) for x in fwd[src]})
    elif cat == "reverse_dep" and src in rev:
        ind = sorted({norm(x) for x in rev[src]})
    elif cat == "symbol_location":
        # 从问题里抽符号名(大写开头标识符),查 classfile/funcfile
        m = re.findall(r"[A-Z_a-z][A-Za-z0-9_]+", c["question"])
        sym = None
        for tok in m:
            if tok in classfile: sym = classfile[tok]; break
            if tok in funcfile: sym = funcfile[tok]; break
        if sym: ind = [sym]  # 文件路径作 gold(与现有一致)
    elif cat == "inheritance":
        m = re.findall(r"[A-Z][A-Za-z0-9_]+", c["question"])
        for tok in m:
            bs, bf = base_of(tok)
            if bs:
                kw = [b for b in bs]
                if bf and classfile.get(bs[0]): pass
                # 加上基类所在文件
                if bs[0] in classfile: kw.append(classfile[bs[0]])
                ind = sorted(set(kw)); break
    if ind is None:
        continue  # 该类 ast 难独立确定(如 indirect/dataflow),留作人工
    # 一致性(独立 gold 是否覆盖 tree-sitter gold 的关键词,归一化后)
    inter = gold_ts & set(ind)
    agree_n += len(inter); tot_n += len(gold_ts)
    if gold_ts != set(ind):
        diffs.append((cid, cat, sorted(gold_ts), ind))
    out.append({"id": cid, "category": cat, "question": c["question"],
                "gold": ", ".join(ind), "gold_kw": ind, "notes": f"(独立 ast 抽取,归一化包名){src}"})

json.dump(out, open(ROOT/"results"/"independent_gold_bundle.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"独立金标准:{len(out)} 条(forward/reverse/symbol/inheritance)")
print(f"与 tree-sitter 金标准 keyword 一致(归一化后):{agree_n}/{tot_n} = {agree_n/tot_n:.1%}")
print(f"\n差异 {len(diffs)} 条(供人工核验):")
for cid, cat, ts, ind in diffs:
    print(f"  {cid}({cat}): tree-sitter={ts}  ast独立={ind}")
