"""M20:跨语言依赖抽取(正则,独立于tree-sitter)+ 建用例 + baseline/full bundle。
Go(gin)/Java(gson)/C(lua)。gold 由正则抽取,关键用例人工抽verify(见 CROSS_LANGUAGE.md)。
输出 results/xlang/<lang>_cases.json + bundle_<lang>_baseline.json / _full.json
"""
import re, json, sys, os
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/"results"/"xlang"; OUT.mkdir(parents=True, exist_ok=True)

SCAFFOLD_FULL = ("你是一个代码仓库依赖分析助手。请仅依据以下检索到的依赖卡片回答问题。"
                 "如果卡片里没有答案,请明确说\"根据给定卡片没有找到\",不要臆造。\n\n")
SCAFFOLD_BASE = ("你是一个代码仓库依赖分析助手。请根据你对该开源项目的了解回答下面的跨文件依赖问题。"
                 "如果不确定,请明确说\"不确定\",不要臆造。\n\n")

def card_text(f, fwd, rev, defs):
    return (f"[依赖卡片] 文件 {f}\n"
            f"它依赖的本仓库文件: {', '.join(sorted(fwd)) or '(无)'}\n"
            f"它被这些本仓库文件依赖: {', '.join(sorted(rev)) or '(无)'}\n"
            f"它内部定义的符号: {', '.join(defs[:25]) or '(无)'}")

def build_lang(lang, files_dict, fwd, rev, defs, symloc, inherit, proj):
    """files_dict: relpath->src; fwd/rev: dict file->set; defs: file->[symbols];
    symloc: symbol->file; inherit: class->(base, basefile)."""
    cases = []
    allfiles = sorted(files_dict)
    # forward_dep
    for f in allfiles:
        if fwd.get(f):
            cases.append({"id":f"{lang}-FWD-{len(cases)}","category":"forward_dep","focal":f,
                "question":f"在 {proj} 项目中,文件 {f} 直接依赖(import/include/引用)了哪些本仓库内的文件?列出文件。",
                "gold":", ".join(sorted(fwd[f])), "gold_kw":[Path(x).name for x in sorted(fwd[f])]})
    # reverse_dep
    for f in allfiles:
        if rev.get(f):
            cases.append({"id":f"{lang}-REV-{len(cases)}","category":"reverse_dep","focal":f,
                "question":f"在 {proj} 项目中,哪些本仓库内的文件依赖(import/include/引用)了 {f}?列出文件。",
                "gold":", ".join(sorted(rev[f])), "gold_kw":[Path(x).name for x in sorted(rev[f])]})
    # symbol_location
    for sym, f in list(symloc.items()):
        cases.append({"id":f"{lang}-LOC-{len(cases)}","category":"symbol_location","focal":f,
            "question":f"在 {proj} 项目中,符号 {sym}(类/类型/函数/结构体)定义在哪个文件里?",
            "gold":f, "gold_kw":[Path(f).name]})
    # inheritance (Java)
    for cls,(base,bf) in inherit.items():
        cases.append({"id":f"{lang}-INH-{len(cases)}","category":"inheritance","focal":symloc.get(cls,"?"),
            "question":f"在 {proj} 项目中,类/接口 {cls} 继承(extends)或实现(implements)了什么?",
            "gold":base, "gold_kw":[base.split('.')[-1]]})
    return cases

def neighborhood_card(focal, fwd, rev, defs):
    nodes=[focal]+sorted(fwd.get(focal,set()))[:6]+sorted(rev.get(focal,set()))[:6]
    seen=[];
    for n in nodes:
        if n not in seen: seen.append(n)
    return "\n\n".join(card_text(n, fwd.get(n,set()), rev.get(n,set()), defs.get(n,[])) for n in seen[:10])

def make_bundles(lang, cases, fwd, rev, defs):
    base, full = [], []
    for c in cases:
        q=c["question"]
        base.append({"id":c["id"],"category":c["category"],"difficulty":"medium","question":q,
            "gold":c["gold"],"notes":"(跨语言用例,正则抽取gold)","gen_prompt":SCAFFOLD_BASE+f"问题:{q}\n请直接回答。"})
        card=neighborhood_card(c["focal"], fwd, rev, defs)
        full.append({"id":c["id"],"category":c["category"],"difficulty":"medium","question":q,
            "gold":c["gold"],"notes":"(跨语言用例,正则抽取gold)","gen_prompt":SCAFFOLD_FULL+card+f"\n\n问题:{q}\n请直接回答。"})
    json.dump(base, open(OUT/f"bundle_{lang}_baseline.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(full, open(OUT/f"bundle_{lang}_full.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(cases, open(OUT/f"{lang}_cases.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)

# ============ GO (gin) ============
def extract_go():
    base=ROOT/"repos"/"go_gin"
    files={p.relative_to(base).as_posix():p.read_text(encoding="utf-8",errors="replace")
           for p in base.glob("*.go") if not p.name.endswith("_test.go")}
    defs=defaultdict(list); symloc={}
    for f,src in files.items():
        for m in re.finditer(r'^type\s+([A-Z]\w+)\s+(?:struct|interface|func|\w)', src, re.M):
            defs[f].append(m.group(1)); symloc.setdefault(m.group(1),f)
        for m in re.finditer(r'^func\s+(?:\([^)]*\)\s+)?([A-Z]\w+)\s*\(', src, re.M):
            defs[f].append(m.group(1)); symloc.setdefault(m.group(1),f)
    fwd=defaultdict(set); rev=defaultdict(set)
    for f,src in files.items():
        body=src
        for sym,deff in symloc.items():
            if deff==f: continue
            if re.search(r'\b'+re.escape(sym)+r'\b', body):
                fwd[f].add(deff); rev[deff].add(f)
    return files,dict(fwd),dict(rev),dict(defs),symloc,{}

# ============ JAVA (gson core) ============
def strip_comments(src):
    src=re.sub(r'/\*.*?\*/','',src,flags=re.S)  # 块注释
    src=re.sub(r'//[^\n]*','',src)               # 行注释
    return src

def extract_java():
    base=ROOT/"repos"/"java_gson"/"gson"/"src"/"main"/"java"/"com"/"google"/"gson"
    srcfiles=[p for p in base.rglob("*.java")
              if not any(x in p.as_posix() for x in ("/test/","extras","examples"))]
    # 用 包路径/类名 作 relpath
    files={}; fqcn2file={}
    for p in srcfiles:
        ap=p.as_posix(); rel=ap[ap.index("com/google/gson"):]
        src=strip_comments(p.read_text(encoding="utf-8",errors="replace")); files[rel]=src
        pkg=re.search(r'^package\s+([\w.]+);',src,re.M)
        cls=re.search(r'\b(?:class|interface|enum)\s+([A-Z]\w+)',src)
        if pkg and cls: fqcn2file[pkg.group(1)+"."+cls.group(1)]=rel
    defs=defaultdict(list); symloc={}; inherit={}
    for f,src in files.items():
        for m in re.finditer(r'\b(?:class|interface|enum)\s+([A-Z]\w+)',src):
            defs[f].append(m.group(1)); symloc.setdefault(m.group(1),f)
        # 类名与 extends/implements 同一声明内绑定(避免内部类错配)
        for m in re.finditer(r'\b(?:public\s+|final\s+|abstract\s+)*(?:class|interface)\s+([A-Z]\w+)(?:<[^>]*>)?\s+(?:extends\s+([A-Z][\w.]+)|implements\s+([A-Z][\w.]+))',src):
            cls=m.group(1); base_=(m.group(2) or m.group(3) or "").strip()
            if base_ and cls not in inherit: inherit[cls]=(base_, None)
    fwd=defaultdict(set); rev=defaultdict(set)
    for f,src in files.items():
        for m in re.finditer(r'^import\s+(?:static\s+)?(com\.google\.gson[\w.]+);',src,re.M):
            fq=m.group(1)
            # 去掉末尾方法名(static import),映射到类文件
            for cand in (fq, fq.rsplit(".",1)[0]):
                if cand in fqcn2file and fqcn2file[cand]!=f:
                    fwd[f].add(fqcn2file[cand]); rev[fqcn2file[cand]].add(f); break
    return files,dict(fwd),dict(rev),dict(defs),symloc,inherit

# ============ C (lua) ============
def extract_c():
    base=ROOT/"repos"/"c_lua"
    files={p.name:p.read_text(encoding="utf-8",errors="replace") for p in base.glob("*.c")}
    hdrs={p.name:p.read_text(encoding="utf-8",errors="replace") for p in base.glob("*.h")}
    allf={**files,**hdrs}
    defs=defaultdict(list); symloc={}
    for f,src in allf.items():
        for m in re.finditer(r'^(?:LUA_API|LUAI_FUNC|static\s+)?\w[\w\s\*]*?\b(\w+)\s*\([^;]*\)\s*\{', src, re.M):
            if m.group(1) not in ('if','for','while','switch','return'):
                defs[f].append(m.group(1)); symloc.setdefault(m.group(1),f)
        for m in re.finditer(r'^(?:typedef\s+)?struct\s+(\w+)\s*\{', src, re.M):
            defs[f].append("struct "+m.group(1)); symloc.setdefault("struct "+m.group(1),f)
    fwd=defaultdict(set); rev=defaultdict(set)
    for f,src in allf.items():
        for m in re.finditer(r'#include\s+"([\w.]+\.h)"', src):
            h=m.group(1)
            if h in allf and h!=f:
                fwd[f].add(h); rev[h].add(f)
    return allf,dict(fwd),dict(rev),dict(defs),symloc,{}

PROJ={"go":"gorilla-gin","java":"google-gson","c":"lua"}
EXTRACT={"go":extract_go,"java":extract_java,"c":extract_c}
for lang in ("go","java","c"):
    files,fwd,rev,defs,symloc,inherit=EXTRACT[lang]()
    cases=build_lang(lang,files,fwd,rev,defs,symloc,inherit,PROJ[lang])
    # 抽样均衡:每类最多取若干,控制总量~25
    import collections
    bycat=collections.defaultdict(list)
    for c in cases: bycat[c["category"]].append(c)
    sel=[]
    caps={"forward_dep":7,"reverse_dep":7,"symbol_location":8,"inheritance":6}
    for cat,lst in bycat.items():
        # 取依赖数适中的(gold不空、不过长)
        lst=[c for c in lst if 1<=len(c["gold_kw"])<=8]
        sel+=lst[:caps.get(cat,6)]
    make_bundles(lang,sel,fwd,rev,defs)
    print(f"{lang}({PROJ[lang]}): {len(files)}文件, 用例 {len(sel)} ", dict(collections.Counter(c['category'] for c in sel)))
print("输出 ->", OUT)
