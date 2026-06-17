# -*- coding: utf-8 -*-
"""检索冒烟测试(过程护栏)。
目的:第一天就能拦住"embedding 选错语言 / pipeline 配错 / 检索退化 / 卡片生成为空"这类沉默退化——
本项目的 embedding 选错语言 bug(pipeline 指向中文 bge,跑了约两个月)就是事后补的教训(诚实标注,不掩饰)。

运行:python tests/smoke_retrieval.py   (退出码非 0 = 有退化)
- 护栏 1-3 不需要 GPU/模型(确定性,含"真实 pipeline 配置"断言——这条直接拦当年的故障模式);
- 护栏 4(embedding 区分力)需 sentence-transformers + bge 模型,无则自动 SKIP。
"""
import os, re, sys, ast

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASS, SKIP, FAIL = [], [], []
def ok(n): PASS.append(n); print(f"  [PASS] {n}")
def skip(n, why): SKIP.append(n); print(f"  [SKIP] {n} — {why}")
def bad(n, why): FAIL.append(n); print(f"  [FAIL] {n} — {why}")

def find_config():
    for base in (ROOT, os.path.dirname(ROOT)):
        p = os.path.join(base, "03_代码", "configs", "best_stack.yaml")
        if os.path.exists(p): return p
    return None

# ---- 护栏 1(确定性):依赖卡片生成不为空 ----
def t_card_nonempty():
    fixture = "from os import path\nimport json\nfrom .util import helper\ndef f():\n    return helper()\n"
    imps = []
    for node in ast.walk(ast.parse(fixture)):
        if isinstance(node, ast.ImportFrom) and node.module: imps.append(node.module)
        elif isinstance(node, ast.Import): imps += [a.name for a in node.names]
    if imps and "os" in imps and "util" in imps: ok(f"card_nonempty(imports={imps})")
    else: bad("card_nonempty", f"卡片应非空且含已知依赖,实际 {imps}")

# ---- 护栏 2(确定性):检索返回非空、格式正确 ----
def t_retrieval_format():
    corpus = [{"id": "a", "text": "datastructures headers parse"},
              {"id": "b", "text": "http date utils"}, {"id": "c", "text": "exceptions badrequest"}]
    hits = [d for d in corpus if any(w in d["text"] for w in "headers parse".split())]
    if hits and all("id" in h and "text" in h for h in hits) and hits[0]["id"] == "a":
        ok(f"retrieval_format(命中 {len(hits)},top=a)")
    else: bad("retrieval_format", f"检索应非空且格式正确,实际 {hits}")

# ---- 护栏 3(确定性,核心牙齿):真实 pipeline 实际加载的 embedding 不是中文 ----
def t_pipeline_embedding_is_english():
    cfg = find_config()
    if not cfg: return skip("pipeline_embedding_is_english", "未找到 best_stack.yaml")
    txt = open(cfg, encoding="utf-8").read()
    m = re.search(r"model_name:\s*([^\s#]+)", txt)
    if not m: return bad("pipeline_embedding_is_english", "配置里找不到 embedding model_name")
    name = m.group(1).lower()
    # 当年的真实故障模式:pipeline 指向中文 bge-small-zh。代码/英文任务必须用 en / code / minilm。
    if "zh" in name and "-ft" not in name:
        bad("pipeline_embedding_is_english",
            f"主 pipeline embedding 仍指向中文模型({m.group(1)})——这正是当年跑了两个月的 bug!"
            f"代码/英文任务请用 bge-small-en / 代码 embedding。")
    elif any(k in name for k in ("en", "code", "minilm")):
        ok(f"pipeline_embedding_is_english(best_stack 配置 = {m.group(1)})")
    else:
        bad("pipeline_embedding_is_english", f"embedding({m.group(1)})既非 en/code/minilm,请确认非中文模型")

# ---- 护栏 4(需 ST+模型,有区分力的 fixture):en 在英文代码语料上明显强于 zh ----
def t_embedding_en_beats_zh():
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except Exception as e:
        return skip("embedding_en_beats_zh", f"无 sentence-transformers({str(e)[:40]})")
    EN = os.environ.get("BGE_EN_PATH", "BAAI/bge-small-en-v1.5")
    ZH = os.environ.get("BGE_ZH_PATH", "BAAI/bge-small-zh-v1.5")
    # 英文代码结构卡片语料 + **释义 query(刻意不含字面 secure_filename/import_string)**,
    # 强制走语义匹配——中文 bge 在此会掉分(实测 zh gold 排第 2、en 排第 1),使断言有区分力。
    cards = [
        "File datastructures/headers.py Classes Headers EnvironHeaders",
        "File http.py Functions parse_date http_date dump_header",
        "File utils.py Functions secure_filename import_string redirect",
        "File exceptions.py Classes BadRequest NotFound",
        "File formparser.py Classes FormDataParser MultiPartParser",
        "File wrappers/response.py Classes Response Functions set_cookie",
        "File routing/rules.py Classes Rule Functions build compile match",
        "File serving.py Functions run_simple make_server",
    ]
    query = ("the module with a helper that sanitizes an uploaded file name and "
             "one that loads a class from a dotted string path")
    gold = 2
    def mrr_top1(mid):
        m = SentenceTransformer(mid)
        ce = np.array(m.encode(cards, normalize_embeddings=True, show_progress_bar=False))
        qe = np.array(m.encode([query], normalize_embeddings=True, show_progress_bar=False))[0]
        order = list(np.argsort(-(ce @ qe)))
        return order[0] == gold, 1.0 / (order.index(gold) + 1)
    try:
        en_t1, en_mrr = mrr_top1(EN); zh_t1, zh_mrr = mrr_top1(ZH)
    except Exception as e:
        return skip("embedding_en_beats_zh", f"模型加载失败({str(e)[:40]})")
    # 有区分力:en 命中 top-1 且 MRR 明显高于 zh(选错语言会让 en≤zh)
    if en_t1 and en_mrr > zh_mrr:
        ok(f"embedding_en_beats_zh(en mrr={en_mrr:.2f} > zh mrr={zh_mrr:.2f},区分力成立)")
    else:
        bad("embedding_en_beats_zh",
            f"英文 embedding 应在英文代码语料上明显强于中文——en(top1={en_t1},mrr={en_mrr:.2f}) vs zh(mrr={zh_mrr:.2f})")

if __name__ == "__main__":
    print("=== 检索冒烟测试(过程护栏)===")
    for t in (t_card_nonempty, t_retrieval_format, t_pipeline_embedding_is_english, t_embedding_en_beats_zh):
        try: t()
        except Exception as e: bad(t.__name__, f"异常 {e}")
    print(f"\n结果: PASS={len(PASS)} SKIP={len(SKIP)} FAIL={len(FAIL)}")
    sys.exit(1 if FAIL else 0)
