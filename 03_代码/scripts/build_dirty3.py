"""M33任务一+二:中性措辞(不暗示"能否静态确定")+ 多项目(CPython/flask/requests)脏用例。
排除"问题措辞与humble对齐"混淆。3条件baseline/strict/humble。gold人工核验。
"""
import ast, re, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results"/"dirty"; OUT.mkdir(parents=True,exist_ok=True)
REPOS={"CPython":ROOT/"repos"/"cpython"/"Lib","flask":ROOT/"repos"/"flask","requests":ROOT/"repos"/"requests"}

def static_card(proj,rel):
    base=REPOS[proj]; src=(base/rel).read_text(encoding="utf-8",errors="replace")
    imps=set()
    try:
        for n in ast.walk(ast.parse(src)):
            if isinstance(n,ast.Import):
                for a in n.names: imps.add(a.name.split(".")[0])
            elif isinstance(n,ast.ImportFrom) and n.module: imps.add(n.module.split(".")[0])
    except SyntaxError: pass
    return f"[依赖卡片] {proj}/{rel}\n它import的模块(静态分析): {', '.join(sorted(imps)) or '(无)'}\n(注:本卡片由静态 import 分析生成)"

SC_STRICT="你是代码依赖分析助手。请仅依据以下依赖卡片回答问题。卡片没有就说\"根据卡片没有找到\",不要臆造。\n\n"
SC_HUMBLE=("你是代码依赖分析助手。以下依赖卡片由**静态分析**生成,**可能不完整**——运行时动态导入、条件导入、反射等依赖可能被遗漏或未标注其条件性。"
           "请**结合卡片与你自己对该项目的了解**作答,对静态分析可能遗漏/误标的依赖要主动指出并说明。\n\n")
SC_BASE="你是代码依赖分析助手。请根据你对该项目的了解回答。不确定就说\"不确定\",不要臆造。\n\n"

# 中性措辞:不含"能否静态确定/是否动态/是硬还是可选"等引导词
cases=[]  # (proj, file, 中性question, gold, type)
def add(*a): cases.append(a)
# 动态——中性问"完整列出会导入/加载的模块(含所有方式)"
add("CPython","pickle.py","完整说明 Lib/pickle.py 在反序列化过程中会加载哪些模块。","除静态 import 外,反序列化时会按被反序列化对象的模块名通过 __import__ 加载模块——该模块名是运行时数据,具体目标随数据而变。","dynamic")
add("CPython","pydoc.py","完整说明 Lib/pydoc.py 在为对象生成文档时会加载哪些模块。","除静态 import 外,会用 importlib.import_module 在运行时按用户查询的对象名加载对应模块,目标随运行时输入而变。","dynamic")
add("flask","cli.py","完整说明 flask/cli.py 运行时会加载哪些模块。","除静态 import 外,会用 importlib 在运行时按用户指定的应用名/路径动态加载应用模块,目标随运行时输入而变。","dynamic")
add("flask","helpers.py","完整说明 flask/helpers.py 实际会用到哪些模块。","除静态 import 外含运行时按名加载的导入,目标运行时定。","dynamic")
# 条件——中性问"准确描述对Y模块依赖的性质"
def cond_cases(proj,maxn):
    base=REPOS[proj]; got=0
    for p in sorted(base.rglob("*.py")):
        if got>=maxn: break
        try: src=p.read_text(encoding="utf-8",errors="replace")
        except: continue
        m=re.search(r'try:\s*\n\s*(?:from \S+ )?import (\w+)\s*\n\s*except ImportError',src)
        if m:
            rel=p.relative_to(base).as_posix(); mod=m.group(1)
            add(proj,rel,f"准确描述 {proj}/{rel} 对 {mod} 模块依赖的性质。",f"{mod} 是条件/可选依赖:在 try/except ImportError 中导入,缺失时降级(置 None 或走备选),并非在所有环境都存在的硬依赖。","conditional")
            got+=1
cond_cases("CPython",10); cond_cases("requests",4); cond_cases("flask",3)

bs=[]; bh=[]; bb=[]
for i,(proj,f,q,gold,typ) in enumerate(cases):
    card=static_card(proj,f); cid=f"D3-{typ[:3]}-{i}"
    base={"id":cid,"category":typ,"difficulty":"hard","question":q,"gold":gold}
    bs.append({**base,"notes":"(中性-strict)","gen_prompt":SC_STRICT+card+f"\n\n问题:{q}\n请直接回答。"})
    bh.append({**base,"notes":"(中性-humble)","gen_prompt":SC_HUMBLE+card+f"\n\n问题:{q}\n请直接回答。"})
    bb.append({**base,"notes":"(中性-baseline)","gen_prompt":SC_BASE+f"问题:{q}\n请直接回答。"})
json.dump(bs,open(OUT/"bundle_d3_strict.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(bh,open(OUT/"bundle_d3_humble.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(bb,open(OUT/"bundle_d3_baseline.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
import collections
print(f"中性措辞脏用例 {len(cases)}:",dict(collections.Counter(c[4] for c in cases)),"项目:",dict(collections.Counter(c[0] for c in cases)))
