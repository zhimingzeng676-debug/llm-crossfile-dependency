"""M30:扩脏场景样本+多类型+3条件(baseline/full_strict只信卡片/full_humble承认卡片可能不全)。
任务一扩样本、任务二脏类型曲线、任务三prompt可救性 一次跑。gold人工核验。
"""
import ast, re, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
LIB=ROOT/"repos"/"cpython"/"Lib"
OUT=ROOT/"results"/"dirty"; OUT.mkdir(parents=True,exist_ok=True)

def static_card(relpath):
    src=(LIB/relpath).read_text(encoding="utf-8",errors="replace")
    imps=set()
    try:
        for n in ast.walk(ast.parse(src)):
            if isinstance(n,ast.Import):
                for a in n.names: imps.add(a.name.split(".")[0])
            elif isinstance(n,ast.ImportFrom) and n.module: imps.add(n.module.split(".")[0])
    except SyntaxError: pass
    return (f"[依赖卡片] 文件 Lib/{relpath}\n它import的模块(静态分析): {', '.join(sorted(imps)) or '(无)'}\n(注:本卡片由静态 import 分析生成)")

SC_STRICT="你是代码依赖分析助手。请仅依据以下依赖卡片回答问题。卡片没有就说\"根据卡片没有找到\",不要臆造。\n\n"
SC_HUMBLE=("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整**——运行时动态导入(__import__/importlib)、"
           "条件导入(try/except ImportError)、反射等依赖可能被遗漏或未标注其条件性。请**结合卡片与你自己对该项目的了解**作答,"
           "对静态分析可能遗漏/误标的依赖要主动指出并说明。\n\n")
SC_BASE="你是代码依赖分析助手。请根据你对 CPython 的了解回答。不确定就说\"不确定\",不要臆造。\n\n"

# 人工核验脏用例(扩充)
cases=[]
def add(f,q,gold,typ): cases.append((f,q,gold,typ))
# 动态 __import__/importlib(静态完全漏)
add("pickle.py","Lib/pickle.py 在 unpickling 时通过 __import__ 动态导入的模块由什么决定?能否静态确定具体模块名?","由被反序列化对象的模块名(运行时数据)决定;无法静态确定(__import__(module) 的 module 是运行时变量)。","dynamic")
add("pydoc.py","Lib/pydoc.py 通过 importlib.import_module 动态导入的模块能否静态确定?","不能;目标是运行时传入的模块名,静态无法确定。","dynamic")
add("inspect.py","Lib/inspect.py 是否存在静态 import 列表之外的运行时动态导入?","存在;用 importlib 在运行时按需导入,目标运行时定。","dynamic")
add("pkgutil.py","Lib/pkgutil.py 是否依赖只能在运行时确定的动态导入(importlib)?","是;按运行时包名动态导入,静态 import 列表不含这些目标。","dynamic")
add("runpy.py","Lib/runpy.py 运行的目标模块能否从静态 import 确定?","不能;runpy 按运行时给定的模块/路径动态加载,目标静态不可知。","dynamic")
add("importlib/__init__.py","在 importlib 包中,模块按名称字符串动态加载——这种依赖能否静态列出?","不能;importlib 的核心就是运行时按字符串加载,依赖目标静态不可枚举。","dynamic")
# 反射/getattr 动态属性
add("operator.py","若代码用 getattr(module, name) 按运行时字符串取属性,该依赖能否静态分析列出?","不能;getattr 的 name 是运行时字符串,静态分析无法确定取的是哪个符号。","reflection")
add("enum.py","通过 getattr/setattr 反射访问的成员依赖,静态 import 卡片能否覆盖?","不能;反射访问的目标运行时定,不在静态 import/符号表里。","reflection")

# 条件 import(静态列为普通依赖,不标可选)— 自动扩充
extra=[]
for p in sorted(LIB.glob("*.py")):
    try: src=p.read_text(encoding="utf-8",errors="replace")
    except: continue
    m=re.search(r'try:\s*\n\s*(?:from \S+ )?import (\w+)\s*\n\s*except ImportError',src)
    if m and len(extra)<14:
        mod=m.group(1)
        extra.append((p.name,f"Lib/{p.name} 对 {mod} 的依赖是硬依赖还是可选/条件依赖(缺失时降级)?",f"可选/条件依赖;{mod} 在 try/except ImportError 中导入,缺失时降级,非硬依赖。","conditional"))
for e in extra: add(*e)

bf_strict=[]; bf_humble=[]; bb=[]
for i,(f,q,gold,typ) in enumerate(cases):
    card=static_card(f); cid=f"D2-{typ[:3]}-{i}"
    base={"id":cid,"category":typ,"difficulty":"hard","question":q,"gold":gold}
    bf_strict.append({**base,"notes":"(脏-strict只信卡片)","gen_prompt":SC_STRICT+card+f"\n\n问题:{q}\n请直接回答。"})
    bf_humble.append({**base,"notes":"(脏-humble承认卡片可能不全)","gen_prompt":SC_HUMBLE+card+f"\n\n问题:{q}\n请直接回答。"})
    bb.append({**base,"notes":"(脏-baseline)","gen_prompt":SC_BASE+f"问题:{q}\n请直接回答。"})
json.dump(bf_strict,open(OUT/"bundle_d2_strict.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(bf_humble,open(OUT/"bundle_d2_humble.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(bb,open(OUT/"bundle_d2_baseline.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
import collections
print(f"扩脏场景 {len(cases)}条:",dict(collections.Counter(t for *_,t in cases)))
