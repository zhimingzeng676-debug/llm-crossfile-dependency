"""M44:为多项目下游实验建 flask(Python ast)+ gson(Java regex)依赖图,
统一成 {forward:{file:[deps]}, reverse:{file:[importers]}} 格式(与 ast_edges_werkzeug 一致)。
独立解析(stdlib ast / regex),与 RAG 卡片解耦。
"""
import ast, re, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/"results"

# ---------- flask: Python ast(包根 = repos/flask) ----------
def build_flask():
    base = ROOT/"repos"/"flask"
    files = [p.relative_to(base).as_posix() for p in base.rglob("*.py")
             if "test" not in p.parts and "tests" not in p.parts and "examples" not in p.parts]
    fileset = set(files)
    def mod_to_file(parts):
        m = "/".join(parts)+".py"; pk = "/".join(parts)+"/__init__.py"
        return m if m in fileset else (pk if pk in fileset else None)
    def resolve_rel(importer, level, module):
        base_parts = importer.split("/")[:-1]
        up = level-1
        tb = base_parts[:len(base_parts)-up] if up <= len(base_parts) else []
        return mod_to_file(tb + (module.split(".") if module else []))
    fwd = {}
    for rel in files:
        try: tree = ast.parse((base/rel).read_text(encoding="utf-8", errors="replace"))
        except SyntaxError: continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                t = resolve_rel(rel, n.level or 0, n.module or "")
                if t and t != rel: fwd.setdefault(rel, set()).add(t)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    p = a.name.split(".")
                    if p and p[0] == "flask":
                        t = mod_to_file(p[1:])
                        if t and t != rel: fwd.setdefault(rel, set()).add(t)
    rev = {}
    for imp, ts in fwd.items():
        for t in ts: rev.setdefault(t, set()).add(imp)
    return {"forward": {k: sorted(v) for k, v in fwd.items()},
            "reverse": {k: sorted(v) for k, v in rev.items()}, "n_files": len(files)}

# ---------- gson: Java regex(类级,import com.google.gson.*) ----------
def build_gson():
    base = ROOT/"repos"/"java_gson"
    files = [p for p in base.rglob("*.java")
             if "test" not in str(p).lower() and "example" not in str(p).lower()]
    # class 简名 -> 文件相对路径
    cls2file = {}
    for p in files:
        cls2file[p.stem] = p.relative_to(base).as_posix()
    fwd = {}
    for p in files:
        rel = p.relative_to(base).as_posix()
        src = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'import\s+(com\.google\.gson\.[\w.]+);', src):
            cls = m.group(1).split(".")[-1]
            tgt = cls2file.get(cls)
            if tgt and tgt != rel: fwd.setdefault(rel, set()).add(tgt)
    rev = {}
    for imp, ts in fwd.items():
        for t in ts: rev.setdefault(t, set()).add(imp)
    return {"forward": {k: sorted(v) for k, v in fwd.items()},
            "reverse": {k: sorted(v) for k, v in rev.items()}, "n_files": len(files)}

fl = build_flask(); json.dump(fl, open(OUT/"ast_edges_flask.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
gs = build_gson(); json.dump(gs, open(OUT/"edges_gson.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
def dist(g, lo, hi): return sum(1 for v in g["reverse"].values() if lo <= len(v) <= hi)
print(f"flask: {fl['n_files']} files, reverse {len(fl['reverse'])}, with 2<=|rev|<=8: {dist(fl,2,8)}")
print(f"gson : {gs['n_files']} files, reverse {len(gs['reverse'])}, with 2<=|rev|<=8: {dist(gs,2,8)}")
