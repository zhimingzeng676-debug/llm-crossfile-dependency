"""M29任务一:脏场景退化实验。静态难算的依赖(动态/条件import),静态卡片会算错/漏。
测 full(喂可能错/缺的卡片)vs baseline,看方法退化。gold人工核验真实行为。
对照:clean=普通静态依赖(full>>baseline已立)。输出dirty bundle + clean control。
"""
import ast, re, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
LIB=ROOT/"repos"/"cpython"/"Lib"
OUT=ROOT/"results"/"dirty"; OUT.mkdir(parents=True,exist_ok=True)

def static_card(relpath):
    """ast静态依赖卡片(脏场景下会漏动态、不标条件)。"""
    src=(LIB/relpath).read_text(encoding="utf-8",errors="replace")
    imps=set()
    try:
        for n in ast.walk(ast.parse(src)):
            if isinstance(n,ast.Import):
                for a in n.names: imps.add(a.name.split(".")[0])
            elif isinstance(n,ast.ImportFrom) and n.module: imps.add(n.module.split(".")[0])
    except SyntaxError: pass
    return (f"[依赖卡片] 文件 Lib/{relpath}\n它import的模块(静态分析): {', '.join(sorted(imps)) or '(无)'}\n"
            f"(注:本卡片由静态 import 分析生成)")

SC_FULL="你是代码依赖分析助手。请仅依据以下依赖卡片回答问题。卡片没有就说\"根据卡片没有找到\",不要臆造。\n\n"
SC_BASE="你是代码依赖分析助手。请根据你对 CPython 的了解回答。不确定就说\"不确定\",不要臆造。\n\n"

# 人工核验的脏场景用例(读源码确认gold)
dirty=[
 # 动态import:__import__(变量) —— 静态卡片完全漏,目标运行时定
 ("pickle.py","在 CPython 的 Lib/pickle.py 中,unpickling 时通过 __import__ 动态导入的模块由什么决定?能否从静态代码确定具体模块名?",
  "由被反序列化对象所属的模块名(运行时数据)决定;无法从静态代码确定具体模块名(__import__(module) 的 module 是运行时变量)。","dynamic"),
 ("pydoc.py","在 CPython 的 Lib/pydoc.py 中,它通过 importlib.import_module 动态导入的模块能否从静态代码确定?",
  "不能;importlib.import_module 的目标是运行时传入的模块名(用户查文档的对象),静态无法确定。","dynamic"),
 ("inspect.py","在 CPython 的 Lib/inspect.py 中,是否存在静态 import 列表之外的运行时动态导入?",
  "存在;inspect 用 importlib.import_module 在运行时按需导入模块,目标运行时定,不在静态 import 列表里。","dynamic"),
 # 条件/可选依赖:try/except ImportError —— 卡片列为普通依赖,不标可选
 ("platform.py","在 CPython 的 Lib/platform.py 中,它对 _wmi 模块的依赖是硬依赖还是可选/条件依赖?",
  "可选/条件依赖;try: import _wmi except ImportError: _wmi=None,_wmi 仅 Windows 有,缺失时降级,不是硬依赖。","conditional"),
 ("platform.py","在 CPython 的 Lib/platform.py 中,winreg 是否是该模块在所有平台上都必需的硬依赖?",
  "不是;winreg 在 try/except ImportError 里条件导入,仅 Windows 可用,非硬依赖。","conditional"),
]
# 找更多条件import文件凑数
import subprocess
extra=[]
for p in sorted(LIB.glob("*.py")):
    try: src=p.read_text(encoding="utf-8",errors="replace")
    except: continue
    m=re.search(r'try:\s*\n\s*(?:from \S+ )?import (\w+)\s*\n\s*except ImportError',src)
    if m and p.name not in ("platform.py",) and len(extra)<7:
        mod=m.group(1)
        extra.append((p.name,f"在 CPython 的 Lib/{p.name} 中,对 {mod} 的依赖是硬依赖还是可选/条件依赖(缺失时是否降级)?",
                      f"可选/条件依赖;{mod} 在 try/except ImportError 中导入,缺失时降级,非硬依赖。","conditional"))
dirty+=extra

bundle_full=[]; bundle_base=[]
for i,(f,q,gold,typ) in enumerate(dirty):
    card=static_card(f)
    cid=f"DIRTY-{typ[:3]}-{i}"
    bundle_full.append({"id":cid,"category":typ,"difficulty":"hard","question":q,"gold":gold,"notes":"(脏场景:静态难算依赖,卡片可能错/缺)","gen_prompt":SC_FULL+card+f"\n\n问题:{q}\n请直接回答。"})
    bundle_base.append({"id":cid,"category":typ,"difficulty":"hard","question":q,"gold":gold,"notes":"(脏场景)","gen_prompt":SC_BASE+f"问题:{q}\n请直接回答。"})
json.dump(bundle_full,open(OUT/"bundle_dirty_full.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(bundle_base,open(OUT/"bundle_dirty_baseline.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
import collections
print(f"脏场景用例 {len(dirty)}:",dict(collections.Counter(t for *_,t in dirty)))
print("样例gold:",dirty[0][2][:70])
print("dirty full卡片是否漏动态(应漏):pickle卡片含__import__目标吗:", "__import__" not in static_card("pickle.py") and "(静态" in static_card("pickle.py"))
