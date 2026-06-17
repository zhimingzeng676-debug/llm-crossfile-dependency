"""M21:CPython 大项目依赖抽取(规模压力测试)。Python(ast)+C(#include)+跨语言(Python↔C扩展)。
输出 results/cpy/cards.jsonl(卡片池,规模量级)+ cpy_cases.json(代表用例,内部+跨界)。
红线:gold 由 ast/regex 独立抽取,关键用例人工抽verify;与已有 Python 库零重叠(CPython 本体)。
"""
import ast, re, json, sys, time
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CPY = ROOT/"repos"/"cpython"
LIB = CPY/"Lib"
CDIRS = [CPY/"Modules", CPY/"Objects", CPY/"Python", CPY/"Include"]
OUT = ROOT/"results"/"cpy"; OUT.mkdir(parents=True, exist_ok=True)
t0=time.time()

# ---------- 1. Python 模块名 -> 文件 解析表 ----------
def mod_name(relpath):
    parts = relpath[:-3].split("/")  # 去 .py
    if parts[-1]=="__init__": parts=parts[:-1]
    return ".".join(parts)
pyfiles = {}  # relpath(Lib/...) -> src
name2py = {}  # dotted -> relpath
for p in LIB.rglob("*.py"):
    if "/test" in p.as_posix() or "test/" in p.as_posix(): continue
    rel = "Lib/"+p.relative_to(LIB).as_posix()
    pyfiles[rel]=p.read_text(encoding="utf-8",errors="replace")
    name2py[mod_name(p.relative_to(LIB).as_posix())]=rel

# ---------- 2. C 文件 + C扩展模块名 -> C文件 ----------
cfiles={}  # relpath -> src
cext={}    # 模块名(如 _json) -> Modules/_json.c
MODULES=CPY/"Modules"
for d in CDIRS:
    for p in list(d.rglob("*.c"))+list(d.rglob("*.h")):
        rel = p.relative_to(CPY).as_posix()
        if "test" in rel.lower() or "clinic" in rel.lower(): continue
        src=p.read_text(encoding="utf-8",errors="replace")
        cfiles[rel]=src
        # 真C扩展模块:Modules/ 顶层 .c 且含 PyInit_(模块初始化)
        if p.parent==MODULES and p.suffix==".c" and "PyInit_" in src:
            cext[p.stem]=rel
print(f"[{time.time()-t0:.0f}s] Python {len(pyfiles)} 文件, C {len(cfiles)} 文件, C扩展模块 {len(cext)}")

# ---------- 3. Python import 边(内部 + 跨语言到C扩展) ----------
pyfwd=defaultdict(set); pyrev=defaultdict(set)
xlang=defaultdict(set)  # pyfile -> set(Modules/*.c)  跨语言边
pydefs=defaultdict(list)
for rel,src in pyfiles.items():
    try: tree=ast.parse(src)
    except SyntaxError: continue
    pkg = rel[4:].rsplit("/",1)[0] if "/" in rel[4:] else ""  # Lib 下包路径
    for n in ast.walk(tree):
        names=[]
        if isinstance(n, ast.Import): names=[a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom) and (n.level or 0)==0 and n.module: names=[n.module]
        elif isinstance(n, ast.ImportFrom) and (n.level or 0)>0 and n.module:
            base=pkg.split("/") if pkg else []
            up=n.level-1; base=base[:len(base)-up] if up<=len(base) else []
            names=[".".join([x for x in base]+[n.module])] if base else [n.module]
        for nm in names:
            # 内部 Python
            tgt=name2py.get(nm) or name2py.get(nm.split(".")[0])
            if tgt and tgt!=rel: pyfwd[rel].add(tgt); pyrev[tgt].add(rel)
            # 跨语言:C扩展模块(_json 等)
            head=nm.split(".")[0]
            if head in cext: xlang[rel].add(cext[head])
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            pydefs[rel].append(n.name)

# ---------- 4. C #include 内部边 ----------
cbyname={Path(f).name:f for f in cfiles}
cfwd=defaultdict(set); crev=defaultdict(set); cdefs=defaultdict(list)
for rel,src in cfiles.items():
    for m in re.finditer(r'#include\s+"([\w./]+\.h)"', src):
        h=Path(m.group(1)).name
        if h in cbyname and cbyname[h]!=rel:
            cfwd[rel].add(cbyname[h]); crev[cbyname[h]].add(rel)
    for m in re.finditer(r'^(?:static\s+)?\w[\w\s\*]*?\b(\w+)\s*\([^;]*\)\s*\{', src, re.M):
        if m.group(1) not in ('if','for','while','switch'): cdefs[rel].append(m.group(1))

# ---------- 5. 卡片池(所有文件,规模量级)----------
def write_cards():
    n=0
    with open(OUT/"cards.jsonl","w",encoding="utf-8") as f:
        for rel in pyfiles:
            dep=sorted(pyfwd.get(rel,set())); use=sorted(pyrev.get(rel,set())); xl=sorted(xlang.get(rel,set()))
            card=(f"[依赖卡片] 文件 {rel}\n它依赖的本仓库Python文件: {', '.join(dep) or '(无)'}\n"
                  f"它被这些文件依赖: {', '.join(use) or '(无)'}\n"
                  f"它依赖的C扩展模块文件(跨语言): {', '.join(xl) or '(无)'}")
            f.write(json.dumps({"id":rel,"text":card},ensure_ascii=False)+"\n"); n+=1
        for rel in cfiles:
            dep=sorted(cfwd.get(rel,set())); use=sorted(crev.get(rel,set()))
            card=(f"[依赖卡片] 文件 {rel}\n它#include的本仓库头文件: {', '.join(dep) or '(无)'}\n"
                  f"它被这些文件#include: {', '.join(use) or '(无)'}")
            f.write(json.dumps({"id":rel,"text":card},ensure_ascii=False)+"\n"); n+=1
    return n
ncards=write_cards()
print(f"[{time.time()-t0:.0f}s] 卡片池总量 {ncards} (werkzeug~100, 放大 {ncards//100}x)")

# 存边供后续(检索/用例)
json.dump({"pyfwd":{k:sorted(v) for k,v in pyfwd.items()},"pyrev":{k:sorted(v) for k,v in pyrev.items()},
           "xlang":{k:sorted(v) for k,v in xlang.items()},"cfwd":{k:sorted(v) for k,v in cfwd.items()},
           "crev":{k:sorted(v) for k,v in crev.items()},"cext":cext},
          open(OUT/"edges.json","w",encoding="utf-8"), ensure_ascii=False)
print(f"[{time.time()-t0:.0f}s] edges.json 已存")
