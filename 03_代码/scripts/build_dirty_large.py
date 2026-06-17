"""M38-40 任务一+三:大样本多项目多语言脏依赖金标准(judge-independent + 与RAG卡片解耦)。
脏类型:conditional(try/except ImportError)、dynamic(__import__/importlib)、reflection(getattr模块分发)、
buildtag(Go //go:build 条件编译)、ifdef(C #ifdef 条件 include)、jreflect(Java 反射动态加载)。
真值由源码独立抽取(regex/人工核验,零 tree-sitter / 零 RAG 卡片),含:
  - card: 静态分析依赖卡片(模型平时所见,扁平 import 列表,不含脏结构)
  - source_snippet: 真实源码片段(脏机制所在,供机理实验的 SOURCE 条件用)
  - gold_complete: 精确补全所需的具体模块 token
  - gold_mech: 精确机制 token(try/except/__import__/getattr...)
  - determinable: 缺失依赖能否从源码静态确定(conditional/buildtag/ifdef=True;纯dynamic/reflection=False)
脏用例真实(取自真实仓库源码),非人造极端。
"""
import ast, re, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/"data"; (ROOT/"results"/"dirty_large").mkdir(parents=True, exist_ok=True)

PY_REPOS = {"CPython": "repos/cpython", "flask": "repos/flask",
            "requests": "repos/requests", "pydantic": "repos/pydantic"}

def static_card(proj, relpath, src):
    """静态分析卡片:ast 抽取顶层 import 名(扁平列表,模拟 RAG 卡片;不含 try/except 结构信息)。"""
    mods = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names: mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module: mods.add(node.module.split(".")[0])
    return f"[依赖卡片] 文件 {proj}/{relpath}\n它 import 的模块(静态分析): {', '.join(sorted(mods))}\n(注:本卡片由静态 import 分析生成)"

cases = []
def add(**kw): cases.append(kw)

# ---------- conditional: try/except ImportError ----------
COND_RE = re.compile(
    r'try:\s*\n((?:[ \t]*(?:from [\w.]+ )?import [^\n]+\n)+)[ \t]*except[ \t]*\(?[^\n:]*ImportError', re.M)
def harvest_conditional(proj, base, cap):
    got = 0
    for p in sorted(Path(base).rglob("*.py")):
        if got >= cap: break
        if any(t in p.parts for t in ("test", "tests")): continue
        try: src = p.read_text(encoding="utf-8", errors="replace")
        except: continue
        m = COND_RE.search(src)
        if not m: continue
        imp_block = m.group(1)
        # 抽取条件导入的具体模块名
        mods = re.findall(r'(?:from ([\w.]+) import|import ([\w.]+))', imp_block)
        names = [a or b for a, b in mods]
        names = [n.split(".")[0] for n in names if n]
        if not names: continue
        card = static_card(proj, p.relative_to(ROOT/"..").as_posix() if False else p.name, src)
        if not card: continue
        rel = p.relative_to(Path(base)).as_posix()
        snippet = m.group(0)[:400]
        add(id=f"L-con-{proj}-{got}", project=proj, rel=rel, dirty_type="conditional",
            card=card, source_snippet=snippet,
            gold_complete=names[:3], gold_mech=["try", "except", "ImportError"],
            determinable=True,
            gold_detect=["可选", "条件", "缺失", "降级", "optional", "并非", "不一定", "未安装", "如果"])
        got += 1
    return got

# ---------- dynamic: __import__ / importlib.import_module ----------
DYN_RE = re.compile(r'(__import__\s*\([^\n)]{0,60}|importlib\.import_module\s*\([^\n)]{0,60})')
def harvest_dynamic(proj, base, cap):
    got = 0
    for p in sorted(Path(base).rglob("*.py")):
        if got >= cap: break
        if any(t in p.parts for t in ("test", "tests")): continue
        try: src = p.read_text(encoding="utf-8", errors="replace")
        except: continue
        m = DYN_RE.search(src)
        if not m: continue
        card = static_card(proj, p.name, src)
        if not card: continue
        rel = p.relative_to(Path(base)).as_posix()
        call = m.group(1)
        mech = "__import__" if "__import__" in call else "importlib"
        add(id=f"L-dyn-{proj}-{got}", project=proj, rel=rel, dirty_type="dynamic",
            card=card, source_snippet=call.strip()[:160],
            gold_complete=["运行时", "运行时数据", "运行时输入", "运行时确定", "运行时决定", "取决于"],
            gold_mech=["__import__", "importlib", "import_module"],
            determinable=False,
            gold_detect=["动态", "运行时", "无法静态", "不能静态", "无法确定", "取决于", "随"])
        got += 1
    return got

# ---------- reflection: getattr 模块分发 ----------
REF_RE = re.compile(r'getattr\(\s*(importlib|sys\.modules|self\.module|module|mod|_module)\b[^\n)]{0,60}')
def harvest_reflection(proj, base, cap):
    got = 0
    for p in sorted(Path(base).rglob("*.py")):
        if got >= cap: break
        if any(t in p.parts for t in ("test", "tests")): continue
        try: src = p.read_text(encoding="utf-8", errors="replace")
        except: continue
        m = REF_RE.search(src)
        if not m: continue
        card = static_card(proj, p.name, src)
        if not card: continue
        rel = p.relative_to(Path(base)).as_posix()
        add(id=f"L-ref-{proj}-{got}", project=proj, rel=rel, dirty_type="reflection",
            card=card, source_snippet=m.group(0).strip()[:160],
            gold_complete=["运行时", "运行时确定", "属性名", "字符串", "取决于"],
            gold_mech=["getattr", "反射"],
            determinable=False,
            gold_detect=["反射", "动态", "运行时", "无法静态", "属性", "取决于", "字符串"])
        got += 1
    return got

for proj, base in PY_REPOS.items():
    cap_c = 26 if proj == "CPython" else 14
    nc = harvest_conditional(proj, base, cap_c)
    nd = harvest_dynamic(proj, base, 10 if proj == "CPython" else 6)
    nr = harvest_reflection(proj, base, 8 if proj == "CPython" else 5)
    print(f"{proj}: conditional {nc}, dynamic {nd}, reflection {nr}")

# ---------- 跨语言:Go / Java / C(regex 抽取,真值人工可核;独立于 tree-sitter & RAG 卡片) ----------
def flat_card(proj, rel, imports):
    return f"[依赖卡片] 文件 {proj}/{rel}\n它依赖的模块/头(静态分析): {', '.join(imports[:12])}\n(注:本卡片由静态分析生成)"

# Go: build-tag 条件编译(determinable) + reflect 动态分发(非determinable)
GO_IMPORTS = re.compile(r'import\s*\(([^)]*)\)', re.S)
def go_imports(src):
    m = GO_IMPORTS.search(src)
    if not m: return []
    return re.findall(r'"([^"]+)"', m.group(1))
def harvest_go(base, cap_tag, cap_ref):
    nt = nr = 0
    for p in sorted(Path(base).rglob("*.go")):
        if "_test" in p.name: continue
        try: src = p.read_text(encoding="utf-8", errors="replace")
        except: continue
        rel = p.relative_to(Path(base)).as_posix()
        imps = [i.split("/")[-1] for i in go_imports(src)]
        mtag = re.search(r'//\s*(?:go:build|\+build)\s+([^\n]+)', src)
        if mtag and nt < cap_tag:
            tag = mtag.group(1).strip()
            add(id=f"L-bld-go-{nt}", project="go_gin", rel=rel, dirty_type="buildtag",
                card=flat_card("go_gin", rel, imps) if imps else f"[依赖卡片] 文件 go_gin/{rel}\n(静态分析)",
                source_snippet=mtag.group(0).strip()[:120],
                gold_complete=[tag.split()[0].replace("!", "")] if tag.split() else [tag],
                gold_mech=["go:build", "+build", "构建标签", "条件编译", "build"],
                determinable=True,
                gold_detect=["条件", "平台", "构建", "build", "仅在", "只在", "特定", "取决于"])
            nt += 1
        elif re.search(r'\breflect\.(ValueOf|TypeOf|New|Call)', src) and nr < cap_ref:
            add(id=f"L-ref-go-{nr}", project="go_gin", rel=rel, dirty_type="reflection",
                card=flat_card("go_gin", rel, imps) if imps else f"[依赖卡片] 文件 go_gin/{rel}\n(静态分析)",
                source_snippet=(re.search(r'reflect\.\w+\([^\n)]{0,40}', src).group(0))[:120],
                gold_complete=["运行时", "运行时类型", "运行时确定", "取决于"],
                gold_mech=["reflect", "反射"],
                determinable=False,
                gold_detect=["反射", "动态", "运行时", "无法静态", "类型", "取决于"])
            nr += 1
    return nt, nr

# Java(gson): 反射动态类加载/类型解析(非determinable)
def java_imports(src):
    return [m.split(".")[-1] for m in re.findall(r'import\s+([\w.]+);', src)]
def harvest_java(base, cap):
    n = 0
    for p in sorted(Path(base).rglob("*.java")):
        if n >= cap: break
        if "test" in str(p).lower(): continue
        try: src = p.read_text(encoding="utf-8", errors="replace")
        except: continue
        m = re.search(r'(Class\.forName|getDeclared(?:Method|Field|Constructor)|\.newInstance\(|TypeToken)', src)
        if not m: continue
        rel = p.relative_to(Path(base)).as_posix()
        add(id=f"L-jref-java-{n}", project="java_gson", rel=rel, dirty_type="reflection",
            card=flat_card("java_gson", rel, java_imports(src)),
            source_snippet=(re.search(r'[^\n]{0,40}' + re.escape(m.group(1)) + r'[^\n]{0,40}', src).group(0)).strip()[:160],
            gold_complete=["运行时", "运行时类型", "运行时确定", "取决于", "字符串"],
            gold_mech=["反射", "reflect", "Class.forName", "getDeclared", "newInstance", "TypeToken"],
            determinable=False,
            gold_detect=["反射", "动态", "运行时", "无法静态", "类型", "取决于", "字符串"])
        n += 1
    return n

# C(lua): #ifdef 条件 include(determinable)
def harvest_c(base, cap):
    n = 0
    CIF = re.compile(r'#if(?:def)?\s+(?:defined\s*\(\s*)?(\w+)\s*\)?[^\n]*\n(?:[^\n#]*\n){0,4}?[ \t]*#\s*include\s*[<"]([\w./]+)[>"]', re.M)
    for p in sorted(Path(base).rglob("*.c")) + sorted(Path(base).rglob("*.h")):
        if n >= cap: break
        try: src = p.read_text(encoding="utf-8", errors="replace")
        except: continue
        m = CIF.search(src)
        if not m: continue
        rel = p.relative_to(Path(base)).as_posix()
        macro, hdr = m.group(1), m.group(2).split("/")[-1].replace(".h", "")
        incs = [h.split("/")[-1] for h in re.findall(r'#\s*include\s*[<"]([\w./]+)[>"]', src)][:10]
        add(id=f"L-ifd-c-{n}", project="c_lua", rel=rel, dirty_type="ifdef",
            card=flat_card("c_lua", rel, incs),
            source_snippet=m.group(0).strip()[:200],
            gold_complete=[hdr, macro],
            gold_mech=["#ifdef", "#if", "条件编译", "宏", "defined"],
            determinable=True,
            gold_detect=["条件", "宏", "平台", "编译", "仅当", "只在", "取决于", "如果定义"])
        n += 1
    return n

gt, gr = harvest_go("repos/go_gin", 8, 6)
jn = harvest_java("repos/java_gson", 10)
cn = harvest_c("repos/c_lua", 8)
print(f"Go: buildtag {gt}, reflect {gr} | Java reflection {jn} | C ifdef {cn}")

import collections
print("\n总:", dict(collections.Counter(c["dirty_type"] for c in cases)),
      "| 按项目:", dict(collections.Counter(c["project"] for c in cases)), "| N =", len(cases))
print("determinable:", dict(collections.Counter(c["determinable"] for c in cases)))
json.dump(cases, open(OUT/"dirty_large.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("写出 data/dirty_large.json")
