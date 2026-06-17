"""M21:从 CPython edges 建代表性用例(内部Python/C + 跨语言)。gold卡片=焦点文件卡片。
选偏冷门模块避免记忆;关键用例人工抽verify。"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
E=json.load(open(ROOT/"results"/"cpy"/"edges.json",encoding="utf-8"))
pyfwd,pyrev,xlang,cfwd,crev=E["pyfwd"],E["pyrev"],E["xlang"],E["cfwd"],E["crev"]
def base(x): return Path(x).name
cases=[]
def add(cat,focal,q,gold_list):
    cases.append({"id":f"CPY-{cat[:3].upper()}-{len(cases)}","category":cat,"focal":focal,
                  "question":q,"gold":", ".join(gold_list),"gold_kw":[base(x) for x in gold_list],"gold_card":focal})

# Python 内部 forward(选依赖数适中、非super famous的)
cand_fwd=[(k,v) for k,v in pyfwd.items() if 2<=len(v)<=6 and "test" not in k]
for k,v in cand_fwd[:8]:
    add("py_forward",k,f"在 CPython 中,{k} 这个文件直接 import 了哪些本仓库内的 Python 文件/模块?列出。",v)
# Python 内部 reverse
cand_rev=[(k,v) for k,v in pyrev.items() if 2<=len(v)<=6]
for k,v in cand_rev[:7]:
    add("py_reverse",k,f"在 CPython 中,哪些本仓库内的 Python 文件 import 了 {k}?列出。",v)
# C 内部 forward(#include)
cand_cf=[(k,v) for k,v in cfwd.items() if 2<=len(v)<=6 and k.endswith(".c")]
for k,v in cand_cf[:7]:
    add("c_forward",k,f"在 CPython 中,{k} 这个 C 文件 #include 了哪些本仓库内的头文件?列出。",v)
# C 内部 reverse
cand_cr=[(k,v) for k,v in crev.items() if 2<=len(v)<=8 and k.endswith(".h")]
for k,v in cand_cr[:6]:
    add("c_reverse",k,f"在 CPython 中,哪些本仓库内的文件 #include 了 {k}?列出几个。",v)
# 跨语言:Python 文件依赖哪个 C 扩展源文件
cand_xl=[(k,v) for k,v in xlang.items() if v]
for k,v in cand_xl[:12]:
    add("xlang",k,f"在 CPython 中,{k} 依赖(import)了哪个 C 扩展模块?该扩展由哪个 C 源文件(Modules/*.c)实现?",v)

json.dump(cases, open(ROOT/"results"/"cpy"/"cpy_cases.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
import collections
print(f"用例 {len(cases)}:", dict(collections.Counter(c['category'] for c in cases)))
for c in cases[:3]+[x for x in cases if x['category']=='xlang'][:2]:
    print(f"  [{c['category']}] {c['focal']} -> gold: {c['gold'][:70]}")
