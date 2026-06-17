"""M27:CPython+Go去循环gold(独立原始行抽取,与原ast-walk/正则边解析不同代码路径)+人工抽验。
诚实:CPython原gold用ast(真解析器);此处独立途径=raw-line grep(不同实现)+人工核验,
非"另一个真解析器",解耦级别弱于lua(gcc)/gson(javalang),如实标注。
"""
import json, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results"/"decouple"; OUT.mkdir(parents=True,exist_ok=True)

# ---------- CPython:raw-line 独立抽取 ----------
def decouple_cpy():
    CPY=ROOT/"repos"/"cpython"
    cs=json.load(open(ROOT/"results"/"cpy"/"cpy_cases.json",encoding="utf-8"))
    # 全文件名集合(判仓库内)
    pyf={p.relative_to(CPY/"Lib").as_posix() for p in (CPY/"Lib").rglob("*.py")}
    cnames={p.name for d in ("Modules","Objects","Python","Include") for p in (CPY/d).rglob("*.[ch]")}
    bundle=[]; agree=tot=0; diffs=[]
    for c in cs:
        focal=c["focal"]; cat=c["category"]; dec=None
        fp=CPY/focal
        if not fp.exists(): continue
        src=fp.read_text(encoding="utf-8",errors="replace")
        if cat=="c_forward":
            # raw #include "x.h"
            dec=sorted({Path(m.group(1)).name for m in re.finditer(r'#include\s+"([\w./]+\.h)"',src) if Path(m.group(1)).name in cnames})
        elif cat=="py_forward":
            # raw import 行 -> 本仓库Lib模块
            mods=set()
            for m in re.finditer(r'^\s*(?:from\s+([.\w]+)\s+import|import\s+([.\w]+))',src,re.M):
                nm=(m.group(1) or m.group(2) or "").lstrip(".")
                for cand in (nm.replace(".","/")+".py", nm.replace(".","/")+"/__init__.py", nm.split(".")[0]+".py"):
                    if cand in pyf: mods.add(Path(cand).name if "/" not in cand else cand.split("/")[-1]); break
            dec=sorted(mods)
        elif cat=="xlang":
            # raw import _X -> Modules/_X.c
            exts=set()
            for m in re.finditer(r'(?:from|import)\s+(_[a-z]\w*)',src):
                if (CPY/"Modules"/(m.group(1)+".c")).exists(): exts.add(m.group(1)+".c")
            dec=sorted(exts)
        if dec is None: continue
        orig=set(c["gold_kw"]); decset=set(dec)
        agree+=len(orig&decset); tot+=len(orig)
        if orig!=decset: diffs.append((c["id"],cat,sorted(orig),dec))
        bundle.append({"id":c["id"],"category":cat,"question":c["question"],
                       "gold":", ".join(dec),"gold_kw":dec,"notes":"(独立raw-line抽取+人工抽验,非原ast途径)"})
    return bundle,agree,tot,diffs

# ---------- Go:raw import + 符号引用(原也是正则,此处raw-line+人工)----------
def decouple_go():
    GIN=ROOT/"repos"/"go_gin"
    cs=json.load(open(ROOT/"results"/"xlang"/"go_cases.json",encoding="utf-8"))
    # 简化:对 symbol_location 用 raw "type X"/"func X" grep 独立核验
    bundle=[]; agree=tot=0; diffs=[]
    allgo={p.name:p.read_text(encoding="utf-8",errors="replace") for p in GIN.glob("*.go") if not p.name.endswith("_test.go")}
    for c in cs:
        if c["category"]!="symbol_location": continue
        # 从问题抽符号名
        m=re.search(r'符号\s+(\w+)',c["question"])
        if not m: continue
        sym=m.group(1)
        # 独立grep:哪个文件 raw 定义了 type/func sym
        deff=[f for f,s in allgo.items() if re.search(r'^(?:type|func(?:\s+\([^)]*\))?)\s+'+re.escape(sym)+r'\b',s,re.M)]
        if not deff: continue
        dec=deff[:1]
        orig=set(c["gold_kw"]); agree+= (1 if Path(dec[0]).name in orig else 0); tot+=1
        if Path(dec[0]).name not in orig: diffs.append((c["id"],"symbol",sorted(orig),dec))
        bundle.append({"id":c["id"],"category":"symbol_location","question":c["question"],
                       "gold":dec[0],"gold_kw":[Path(dec[0]).name],"notes":"(独立raw-line grep符号定义+人工)"})
    return bundle,agree,tot,diffs

for name,fn in [("cpy",decouple_cpy),("go",decouple_go)]:
    b,a,t,d=fn()
    json.dump(b,open(OUT/f"bundle_{name}_dec.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"[{name}] 去循环gold {len(b)}条;独立raw-line vs 原gold一致 {a}/{t} = {a/t:.1%}" if t else f"[{name}] {len(b)}条(无可比)")
    for did,cat,o,dd in d[:4]: print(f"    差异 {did}({cat}): 原{o} vs 独立{dd}")
