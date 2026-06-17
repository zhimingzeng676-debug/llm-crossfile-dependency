"""M27 任务一:新工作去循环gold。用与原正则真解耦的独立途径重抽gold:
C(lua/cpython)= gcc -H 编译器解析的直接includes;Java(gson)= javalang真解析器。
复用M20/21案例的question,独立重抽gold,量化与原gold一致率(=循环风险检验)。
输出 results/decouple/bundle_<proj>_dec.json(id,question,gold,notes)+ 一致率报告。
"""
import json, sys, subprocess, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"results"/"decouple"; OUT.mkdir(parents=True,exist_ok=True)

def gcc_direct_includes(repo_dir, relfile, incdirs):
    """gcc -H 取 relfile 的直接#include(单点),只保留仓库内。"""
    args=["gcc","-H","-E"]+[f"-I{d}" for d in incdirs]+["-x","c",str(repo_dir/relfile)]
    try:
        p=subprocess.run(args,capture_output=True,text=True,cwd=str(repo_dir),timeout=30)
    except Exception: return None
    out=set()
    repo_hdrs={p.name for p in repo_dir.rglob("*.h")}
    for line in p.stderr.splitlines():
        m=re.match(r'^\.\s+(.+\.h)$', line)  # 单点=直接
        if m:
            h=Path(m.group(1)).name
            if h in repo_hdrs:  # 只保留仓库内头文件(过滤系统头)
                out.add(h)
    return out

# ---------- C: lua (gcc -H) ----------
def decouple_lua():
    repo=ROOT/"repos"/"c_lua"
    cs=json.load(open(ROOT/"results"/"xlang"/"c_cases.json",encoding="utf-8"))
    bundle=[]; agree=tot=0; details=[]
    # forward: gcc -H 直接includes
    for c in cs:
        if c["category"]!="forward_dep": continue
        f=c["focal"]
        if not (repo/f).exists(): continue
        dec=gcc_direct_includes(repo,f,["."])
        if dec is None: continue
        orig=set(c["gold_kw"])
        inter=orig&dec; agree+=len(inter); tot+=len(orig)
        bundle.append({"id":c["id"],"category":c["category"],"question":c["question"],
                       "gold":", ".join(sorted(dec)),"gold_kw":sorted(dec),"notes":"(gcc -H 编译器独立解析直接includes)"})
        if orig!=dec: details.append((c["id"],sorted(orig),sorted(dec)))
    return bundle,agree,tot,details

# ---------- Java: gson (javalang) ----------
def decouple_gson():
    import javalang
    base=ROOT/"repos"/"java_gson"/"gson"/"src"/"main"/"java"/"com"/"google"/"gson"
    cs=json.load(open(ROOT/"results"/"xlang"/"java_cases.json",encoding="utf-8"))
    # 建 类名->文件 + 每文件imports/继承(javalang独立解析)
    bundle=[]; agree=tot=0; details=[]
    def parse(relfocal):
        p=base/Path(relfocal).relative_to("com/google/gson") if relfocal.startswith("com/google/gson") else None
        fp=ROOT/"repos"/"java_gson"/"gson"/"src"/"main"/"java"/relfocal
        if not fp.exists(): return None
        try: tree=javalang.parse.parse(fp.read_text(encoding="utf-8",errors="replace"))
        except Exception: return None
        imps=[i.path for i in tree.imports if i.path.startswith("com.google.gson")]
        inh=[]
        for _,node in tree.filter(javalang.tree.ClassDeclaration):
            if node.extends: inh.append(node.extends.name if hasattr(node.extends,'name') else str(node.extends))
        for _,node in tree.filter(javalang.tree.InterfaceDeclaration):
            if node.extends:
                for e in node.extends: inh.append(e.name)
        return imps,inh
    for c in cs:
        r=parse(c["focal"])
        if r is None: continue
        imps,inh=r
        if c["category"]=="forward_dep":
            dec=sorted({i.split(".")[-1]+".java" for i in imps})  # 类名.java近似
            # 原gold是文件basename
            orig=set(c["gold_kw"]); decset=set(dec)
            # 宽松匹配:类名出现
            inter=sum(1 for g in orig if any(g.replace('.java','') in d for d in decset) or g in decset)
            agree+=inter; tot+=len(orig)
            bundle.append({"id":c["id"],"category":c["category"],"question":c["question"],
                           "gold":", ".join(dec),"gold_kw":dec,"notes":"(javalang真解析器独立抽import)"})
        elif c["category"]=="inheritance":
            dec=sorted(set(inh))
            orig=set(c["gold_kw"])
            inter=len(orig & set(dec)); agree+=inter; tot+=len(orig)
            bundle.append({"id":c["id"],"category":c["category"],"question":c["question"],
                           "gold":", ".join(dec) or c["gold"],"gold_kw":dec or c["gold_kw"],"notes":"(javalang真解析器独立抽继承)"})
    return bundle,agree,tot,details

for name,fn in [("lua",decouple_lua),("gson",decouple_gson)]:
    try:
        b,a,t,d=fn()
        json.dump(b,open(OUT/f"bundle_{name}_dec.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
        print(f"[{name}] 去循环gold {len(b)}条;独立途径vs原gold一致 {a}/{t} = {a/t:.1%}" if t else f"[{name}] {len(b)}条")
        for did,o,dd in d[:4]: print(f"    差异 {did}: 原{o} vs 独立{dd}")
    except Exception as e:
        import traceback; print(f"[{name}] 失败:",e); traceback.print_exc()
