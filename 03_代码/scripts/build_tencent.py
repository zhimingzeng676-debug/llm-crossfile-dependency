"""M26:腾讯开源 rapidjson(C++头库)依赖抽取 + 用例 + baseline/full bundle。正则,人工抽verify。
诚实:腾讯核心生产代码私有不可得,这里用其开源项目作甲方场景最接近旁证。
"""
import re, json, sys
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
ROOT=Path(__file__).resolve().parent.parent
INC=ROOT/"repos"/"tencent_rapidjson"/"include"
OUT=ROOT/"results"/"xlang"; OUT.mkdir(parents=True,exist_ok=True)
files={}
for p in INC.rglob("*.h"):
    files[p.relative_to(INC).as_posix()]=p.read_text(encoding="utf-8",errors="replace")
# #include 边(resolve 相对路径)
fwd=defaultdict(set); rev=defaultdict(set); defs=defaultdict(list); symloc={}
for rel,src in files.items():
    d=str(Path(rel).parent)
    for m in re.finditer(r'#include\s+"([\w./]+\.h)"', src):
        inc=m.group(1)
        for cand in ([ (Path(d)/inc).as_posix() if d!="." else inc, inc ]):
            cand=cand.replace("rapidjson/","") if cand.startswith("rapidjson/") and cand not in files else cand
        # 尝试:相对当前目录 / 直接 / 去internal前缀
        cands=[inc, (Path(d)/inc).as_posix() if d!="." else inc]
        tgt=next((c for c in cands if c in files and c!=rel), None)
        if tgt: fwd[rel].add(tgt); rev[tgt].add(rel)
    for m in re.finditer(r'^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+([A-Z]\w+)', src, re.M):
        defs[rel].append(m.group(1)); symloc.setdefault(m.group(1),rel)

SC_FULL=("你是一个代码仓库依赖分析助手。请仅依据以下检索到的依赖卡片回答问题。如果卡片里没有答案,请明确说\"根据给定卡片没有找到\",不要臆造。\n\n")
SC_BASE=("你是一个代码仓库依赖分析助手。请根据你对 Tencent/rapidjson 项目的了解回答下面的跨文件依赖问题。不确定请明确说,不要臆造。\n\n")
def card(f):
    return (f"[依赖卡片] 头文件 rapidjson/{f}\n它#include的本仓库头文件: {', '.join(sorted(fwd.get(f,set()))) or '(无)'}\n"
            f"它被这些头文件#include: {', '.join(sorted(rev.get(f,set()))) or '(无)'}\n内部定义的类/结构体: {', '.join(defs.get(f,[])[:15]) or '(无)'}")
def neigh(f):
    ns=[f]+sorted(fwd.get(f,set()))[:5]+sorted(rev.get(f,set()))[:5]
    out=[]
    for n in ns:
        if n not in out: out.append(n)
    return out[:9]

cases=[]
def add(cat,f,q,gold):
    cases.append({"id":f"tx-{cat[:3]}-{len(cases)}","category":cat,"focal":f,"question":q,
                  "gold":", ".join(gold),"gold_kw":[Path(x).name for x in gold]})
for f in sorted(files):
    if 2<=len(fwd.get(f,set()))<=6: add("forward_dep",f,f"在 Tencent/rapidjson 中,头文件 rapidjson/{f} 直接 #include 了哪些本仓库内的头文件?",sorted(fwd[f]))
for f in sorted(files):
    if 2<=len(rev.get(f,set()))<=7: add("reverse_dep",f,f"在 Tencent/rapidjson 中,哪些本仓库头文件 #include 了 rapidjson/{f}?列出几个。",sorted(rev[f]))
for sym,f in list(symloc.items()):
    add("symbol_location",f,f"在 Tencent/rapidjson 中,类/结构体 {sym} 定义在哪个头文件里?",[f])
# 均衡抽样 ~24
import collections
byc=collections.defaultdict(list)
for c in cases: byc[c["category"]].append(c)
sel=[]
for cat,cap in [("forward_dep",8),("reverse_dep",8),("symbol_location",8)]:
    sel+= [c for c in byc[cat] if 1<=len(c["gold_kw"])<=8][:cap]
base,full=[],[]
for c in sel:
    base.append({"id":c["id"],"category":c["category"],"difficulty":"medium","question":c["question"],"gold":c["gold"],"notes":"(腾讯rapidjson,正则gold)","gen_prompt":SC_BASE+f"问题:{c['question']}\n请直接回答。"})
    full.append({"id":c["id"],"category":c["category"],"difficulty":"medium","question":c["question"],"gold":c["gold"],"notes":"(腾讯rapidjson)","gen_prompt":SC_FULL+"\n\n".join(card(n) for n in neigh(c["focal"]))+f"\n\n问题:{c['question']}\n请直接回答。"})
json.dump(base,open(OUT/"bundle_tx_baseline.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(full,open(OUT/"bundle_tx_full.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
json.dump(sel,open(OUT/"tx_cases.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"rapidjson {len(files)}头文件,用例{len(sel)}:",dict(collections.Counter(c['category'] for c in sel)))
for c in sel[:2]+[x for x in sel if x['category']=='reverse_dep'][:1]: print(f"  [{c['category']}] {c['focal']} -> {c['gold'][:60]}")
