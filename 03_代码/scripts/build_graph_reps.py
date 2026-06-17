"""M19:图表示梯度 B0/B1/B2 构建器(从 ast 解耦边,控制变量=同焦点邻域只换格式)。
B0=1-hop文本投影(现状);B1=类型化三元组;B2=B0+多跳传递物化。
产出 bundle_B0/B1/B2.json(gen_prompt+question+gold+notes),覆盖去循环金标准40条+扩充indirect。
"""
import json, sys, ast
from pathlib import Path
from collections import deque
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
E = json.load(open(ROOT/"results"/"ast_edges_werkzeug.json", encoding="utf-8"))
fwd = {k:set(v) for k,v in E["forward"].items()}
rev = {k:set(v) for k,v in E["reverse"].items()}
classfile = E["classfile"]
gold40 = json.load(open(ROOT/"results"/"goldset_decoupled.json", encoding="utf-8"))
cs = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT/"data"/"testcases_werkzeug.jsonl",encoding="utf-8") if l.strip() and not l.startswith("//")}

# 类继承(ast)：file -> [(class, [bases_resolved_file])]
import_alias = {}  # (file) -> {alias: (realname, realfile)} 简化：扫 from X import Y as Z
WZ = ROOT/"repos"/"werkzeug"
classes_in = {}  # file -> [classnames]
class_bases = {}  # (class,file) -> [(basename, basefile|None)]
for k,v in E["bases"].items():
    nm, f = k.rsplit("@",1)
    classes_in.setdefault(f, []).append(nm)
# 解析每文件 import as 别名 -> 真实文件(用于继承基类定位)
def resolve_base_file(importer_file, basename):
    # 从 ast 重新读该文件的 importfrom 找 basename 来源
    p = WZ/importer_file
    try: tree = ast.parse(p.read_text(encoding="utf-8",errors="replace"))
    except: return None
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                local = a.asname or a.name
                if local == basename:
                    # 解析相对模块到文件
                    parts_file = importer_file.split("/")[:-1]
                    up = (n.level or 0)-1
                    base = parts_file[:len(parts_file)-up] if up<=len(parts_file) else []
                    mod = (n.module or "").split(".") if n.module else []
                    cand = "/".join(base+mod)+".py"; cand2="/".join(base+mod)+"/__init__.py"
                    from_file = cand if cand in classfile.values() or (WZ/cand).exists() else (cand2 if (WZ/cand2).exists() else None)
                    return from_file
    return classfile.get(basename)

def norm(rel):
    return rel.split("/")[-2] if rel.endswith("/__init__.py") else Path(rel).stem

# ---------- 三种卡片格式 ----------
def card_B0(f):
    deps = sorted(fwd.get(f,[])); users = sorted(rev.get(f,[]))
    cls = classes_in.get(f, [])
    return (f"[依赖图卡片] 文件 {f}\n"
            f"它依赖(import)的仓库内文件: {', '.join(deps) or '(无)'}\n"
            f"它被这些文件依赖/使用: {', '.join(users) or '(无)'}\n"
            f"文件内定义的类: {', '.join(cls) or '(无)'}")

def card_B1(f):
    lines = [f"[依赖三元组] 文件节点 {f}"]
    for d in sorted(fwd.get(f,[])): lines.append(f"({f}, imports, {d})")
    for u in sorted(rev.get(f,[])): lines.append(f"({u}, imports, {f})")
    for c in classes_in.get(f, []): lines.append(f"({f}, defines_class, {c})")
    return "\n".join(lines)

def transitive_paths(start, maxhop=3):
    """BFS 多跳路径:返回 {target: [path...]}(>=2跳)。"""
    paths = {}
    q = deque([(start,[start])]); seen={start}
    while q:
        node, path = q.popleft()
        if len(path)-1 >= maxhop: continue
        for m in sorted(fwd.get(node,[])):
            if m in seen: continue
            np = path+[m]
            if len(np)-1 >= 2: paths.setdefault(m, np)
            seen.add(m); q.append((m,np))
    return paths

def card_B2(f):
    base = card_B0(f)
    tp = transitive_paths(f)
    if tp:
        lines = ["多跳传递依赖(间接可达,含中间路径):"]
        for tgt, path in list(tp.items())[:20]:
            lines.append("  " + " → ".join(path))
        return base + "\n" + "\n".join(lines)
    return base + "\n多跳传递依赖: (无间接可达)"

def subgraph_nodes(focal, cap=24):
    """围绕 focal 的连通子图节点。顺序:focal → 正向1-hop → 正向2-hop(间接答案所在,优先)→ 反向1-hop。"""
    nodes=[focal]
    fwd1=sorted(fwd.get(focal,[]))
    for n in fwd1:
        if n not in nodes: nodes.append(n)
    for n in fwd1:  # 正向 2-hop(间接可达,优先纳入)
        for m in sorted(fwd.get(n,[])):
            if m not in nodes and len(nodes)<cap: nodes.append(m)
    for n in sorted(rev.get(focal,[])):  # 反向 1-hop(reverse 用例需要)
        if n not in nodes and len(nodes)<cap: nodes.append(n)
    return nodes[:cap]

def card_B3(focal):
    """B3 真子图检索:序列化 focal 周围连通子图(节点集 + 全部内部有向边),非独立卡片/非单根路径。"""
    S=set(subgraph_nodes(focal)); nodes=subgraph_nodes(focal)
    edges=[(u,v) for u in nodes for v in sorted(fwd.get(u,[])) if v in S]
    lines=[f"围绕 {focal} 检索出的依赖子图(连通结构):",
           f"子图节点({len(nodes)}个): {', '.join(nodes)}",
           "子图内的依赖边(A imports B,含节点间所有互联):"]
    for u,v in edges: lines.append(f"  ({u}, imports, {v})")
    return "\n".join(lines)

CARD = {"B0":card_B0, "B1":card_B1, "B2":card_B2}

SCAFFOLD = ("你是一个代码仓库分析助手。请仅依据以下检索到的依赖图信息回答问题。"
            "如果信息里没有答案,请明确说\"根据给定信息没有找到\",不要臆造。\n\n")

def neighborhood(focal):
    """焦点文件 + 1-hop 邻居文件(去重,封顶),三表示用同一节点集。"""
    nodes = [focal]
    for n in sorted(fwd.get(focal,[]))[:6] + sorted(rev.get(focal,[]))[:6]:
        if n not in nodes: nodes.append(n)
    return nodes[:10]

def build_prompt(rep, focal, question):
    if rep=="B3":
        return SCAFFOLD + card_B3(focal) + f"\n\n问题:{question}\n请直接回答。"
    nodes = neighborhood(focal)
    cards = "\n\n".join(CARD[rep](n) for n in nodes)
    return SCAFFOLD + cards + f"\n\n问题:{question}\n请直接回答。"

# ---------- 扩充 indirect 案例(ast 传递闭包,解耦 gold)----------
def expand_indirect(k=10):
    out=[]
    starts=["wrappers/response.py","wrappers/request.py","routing/map.py","sansio/http.py","formparser.py"]
    for s in starts:
        tp = transitive_paths(s)
        for tgt, path in tp.items():
            if len(path)>=3 and len(out)<k:  # 至少2跳(经>=1中介)
                inter = path[1]  # 第一个中间节点
                q=f"在 werkzeug 中,{s} 是否(间接)依赖 {tgt}?如果是,这条依赖路径恰好经过哪个直接中间文件(写出中间文件路径)?"
                out.append({"id":f"INDX-{len(out)+1:02d}","category":"indirect_dep","focal":s,
                            "question":q,"gold":inter,"gold_kw":[norm(inter),inter],
                            "notes":f"(ast传递闭包,解耦)路径 {' → '.join(path)};中介={inter}"})
    return out

# ---------- 组装三套 bundle ----------
indirect_extra = expand_indirect(10)
cases=[]
for g in gold40:
    c=cs[g["id"]]; focal=(c.get("expected_sources") or [None])[0]
    if not focal: continue
    cases.append({"id":g["id"],"category":c["category"],"focal":focal,"question":g["question"],
                  "gold":g["gold"],"notes":g["notes"]})
for ix in indirect_extra:
    cases.append({"id":ix["id"],"category":"indirect_dep","focal":ix["focal"],"question":ix["question"],
                  "gold":ix["gold"],"notes":ix["notes"]})

REPS_TO_BUILD = ("B3",)  # M22:只新增 B3,B0-B2 沿用 M19
for rep in REPS_TO_BUILD:
    bundle=[]
    for c in cases:
        bundle.append({"id":c["id"],"category":c["category"],"difficulty":cs.get(c["id"],{}).get("difficulty","medium"),
                       "question":c["question"],"gold":c["gold"],"notes":c["notes"],
                       "gen_prompt":build_prompt(rep,c["focal"],c["question"])})
    json.dump(bundle, open(ROOT/"results"/f"bundle_{rep}.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
import collections
print(f"案例 {len(cases)} 条:", dict(collections.Counter(c['category'] for c in cases)))
print("生成 bundle_B3.json")
print("\n=== 样例:IND-01 四表示 gen_prompt 长度 ===")
for rep in ("B0","B1","B2","B3"):
    b={x['id']:x for x in json.load(open(ROOT/'results'/f'bundle_{rep}.json',encoding='utf-8'))}
    print(rep, "IND-01 prompt len:", len(b['IND-01']['gen_prompt']))
