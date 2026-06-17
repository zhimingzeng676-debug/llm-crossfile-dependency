"""
M58 Task1 (CPU): build judge-independent blind-spot WARNING dataset from real repos.
Positive = a function whose body contains a genuine DYNAMIC dependency mechanism
(static analysis would miss the target): importlib/__import__, getattr/setattr with
non-constant attr, __subclasses__, entry_points/load_entry_point, pkgutil.iter_modules,
eval/exec, plugin-register decorators. Negative = a function with calls/imports but NO
such mechanism (purely static). Balanced. Gold is AST-structural (NOT the leaky static
IMPORT analyzer). Also flags narrow-keyword presence (for keyword-baseline / beyond-kw
subset) and emits a RENAMED variant (identifiers->generic) for the memory test.
"""
import os, re, ast, json, hashlib, random
REPOS=r"D:\claude\59\pilot_devtruth\repos_hist"; OUT=r"D:\claude\59\pilot_devtruth\task3"
def hk(s): return hashlib.md5(s.encode()).hexdigest()

NARROW_KW=re.compile(r"\b(__import__|importlib|getattr|eval|exec)\b")  # baseline's fixed list

def dyn_mechanisms(fnode, src):
    """return set of dynamic-mechanism tags found in a function node."""
    tags=set()
    for n in ast.walk(fnode):
        if isinstance(n, ast.Call):
            f=n.func
            name=""
            if isinstance(f, ast.Attribute): name=f.attr
            elif isinstance(f, ast.Name): name=f.id
            if name in ("import_module","__import__"): tags.add("importlib")
            if name=="getattr" and len(n.args)>=2 and not isinstance(n.args[1], ast.Constant): tags.add("getattr_dyn")
            if name=="setattr" and len(n.args)>=2 and not isinstance(n.args[1], ast.Constant): tags.add("setattr_dyn")
            if name=="__subclasses__": tags.add("subclasses")
            if name in ("load_entry_point","iter_entry_points","entry_points"): tags.add("entry_points")
            if name in ("iter_modules","walk_packages"): tags.add("pkgutil")
            if name in ("eval","exec"): tags.add("eval_exec")
        if isinstance(n, ast.Attribute) and n.attr=="__subclasses__": tags.add("subclasses")
    # register/plugin decorator
    for d in getattr(fnode,"decorator_list",[]):
        dt=ast.get_source_segment(src,d) or ""
        if re.search(r"register|plugin|hook|provider", dt, re.I): tags.add("register_decorator")
    return tags

def has_static_import_or_call(fnode):
    for n in ast.walk(fnode):
        if isinstance(n,(ast.Import,ast.ImportFrom,ast.Call)): return True
    return False

def rename_src(src):
    """rename identifiers (func/arg/var names) to generic tokens, keep structure+dynamic builtins."""
    try: tree=ast.parse(src)
    except Exception: return src
    KEEP={"importlib","import_module","__import__","getattr","setattr","eval","exec",
          "__subclasses__","load_entry_point","entry_points","iter_entry_points",
          "iter_modules","walk_packages","self","cls","os","sys","re"}
    names={}
    def gen(orig):
        if orig in KEEP or orig.startswith("__"): return orig
        if orig not in names: names[orig]=f"v{len(names)}"
        return names[orig]
    class R(ast.NodeTransformer):
        def visit_FunctionDef(self,n):
            n.name=gen(n.name); self.generic_visit(n); return n
        def visit_Name(self,n):
            n.id=gen(n.id); return n
        def visit_arg(self,n):
            n.arg=gen(n.arg); return n
    try:
        import ast as _a
        return _a.unparse(R().visit(ast.parse(src)))
    except Exception:
        return src

random.seed(0)
pos=[]; neg=[]
projects=[p for p in os.listdir(REPOS) if os.path.isdir(os.path.join(REPOS,p,".git"))]
for proj in projects:
    root=os.path.join(REPOS,proj)
    pyfiles=[]
    for dp,_,fns in os.walk(root):
        if ".git" in dp.replace("\\","/").split("/"): continue
        for fn in fns:
            if fn.endswith(".py"): pyfiles.append(os.path.join(dp,fn))
    random.shuffle(pyfiles)
    ppos=0; pneg=0
    for fp in pyfiles:
        if ppos>=12 and pneg>=12: break
        try: src=open(fp,encoding="utf-8",errors="replace").read()
        except Exception: continue
        try: tree=ast.parse(src)
        except Exception: continue
        rel=os.path.relpath(fp,root).replace("\\","/")
        for fnode in [n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]:
            fsrc=ast.get_source_segment(src,fnode)
            if not fsrc or not (15<len(fsrc)<2000): continue
            tags=dyn_mechanisms(fnode,src)
            if tags and ppos<12:
                pos.append({"project":proj,"file":rel,"func":fnode.name,"label":1,
                            "tags":sorted(tags),"narrow_kw":bool(NARROW_KW.search(fsrc)),
                            "code":fsrc,"code_renamed":rename_src(fsrc)}); ppos+=1
            elif (not tags) and has_static_import_or_call(fnode) and pneg<12:
                neg.append({"project":proj,"file":rel,"func":fnode.name,"label":0,
                            "tags":[],"narrow_kw":bool(NARROW_KW.search(fsrc)),
                            "code":fsrc,"code_renamed":rename_src(fsrc)}); pneg+=1
n=min(len(pos),len(neg))
random.shuffle(pos); random.shuffle(neg)
data=pos[:n]+neg[:n]; random.shuffle(data)
for i,d in enumerate(data): d["id"]=i
json.dump(data, open(os.path.join(OUT,"blindspot_dataset.json"),"w"), indent=1)
# stats
from collections import Counter
print(f"positives={len(pos)} negatives={len(neg)} balanced_total={len(data)} (n={n} each)")
print("positive narrow_kw present:", sum(1 for d in pos[:n] if d['narrow_kw']),"/",n,
      "(beyond-keyword positives:", sum(1 for d in pos[:n] if not d['narrow_kw']),")")
print("negative narrow_kw present (keyword-baseline FALSE POSITIVES):", sum(1 for d in neg[:n] if d['narrow_kw']),"/",n)
print("positive mechanism tags:", Counter(t for d in pos[:n] for t in d['tags']))
