"""M14:构造对比学习训练数据(微调检索器 embedding)。
从训练项目(flask/click/jinja2/requests)程序化生成 (查询, 正确依赖卡片) 正样本对,
并采难负样本(同包/同目录的兄弟卡片,语义近但答案错)。**werkzeug 严格留出,零参与。**

输出 data/retriever_train.jsonl,每行 {"query","positive","hard_neg"}。
负样本策略:① in-batch 随机负(训练时由 MultipleNegativesRankingLoss 自动提供);
            ② 显式难负(本脚本采样:与正样本同目录的另一张卡片)。

用法:python scripts/build_retriever_data.py
"""

import collections
import json
import random

from _common import PROJECT_ROOT
from repomind_lab.chunking import build_chunks
from repomind_lab.repo_parser import parse_repo

TRAIN_REPOS = ["flask", "click", "jinja2", "requests"]
HOLDOUT = "werkzeug"  # 红线:绝不参与
random.seed(14)


def file_cards(repo_path):
    """source -> 文件依赖卡片文本;(class_name,file) -> 类卡片文本。"""
    chunks = build_chunks(repo_path, strategy="function", include_graph_cards=True)
    fcards, ccards = {}, {}
    for c in chunks:
        if c.kind != "graph":
            continue
        if c.chunk_id.startswith("graph:file:"):
            fcards[c.source] = c.text
        elif c.chunk_id.startswith("graph:class:"):
            # chunk_id = graph:class:{file}:{name}
            name = c.chunk_id.rsplit(":", 1)[-1]
            ccards[(name, c.source)] = c.text
    return fcards, ccards


def dir_of(path):
    return path.rsplit("/", 1)[0] if "/" in path else ""


def main():
    pairs = []
    for repo in TRAIN_REPOS:
        rp = PROJECT_ROOT / "repos" / repo
        assert HOLDOUT not in str(rp), "隔离红线"
        g = parse_repo(rp)
        fcards, ccards = file_cards(rp)
        edges = g.import_edges()
        deps_of, importers_of = collections.defaultdict(set), collections.defaultdict(set)
        for a, b in edges:
            deps_of[a].add(b); importers_of[b].add(a)
        fan_in = collections.Counter(b for a, b in edges)
        fan_out = collections.Counter(a for a, b in edges)
        all_files = list(fcards)

        def hard_neg(target_file):
            """同目录的另一张文件卡片做难负;没有则随机一张。"""
            sibs = [f for f in all_files if dir_of(f) == dir_of(target_file) and f != target_file]
            pool = sibs or [f for f in all_files if f != target_file]
            return fcards[random.choice(pool)] if pool else ""

        n0 = len(pairs)
        # reverse_dep:扇入高的文件 → 正样本是该文件自己的卡片(含"被依赖"行)
        for m, _ in fan_in.most_common(12):
            if m in fcards:
                pairs.append({"query": f"在 {repo} 中,哪些文件 import(依赖)了 {m}?请尽量列全。",
                              "positive": fcards[m], "hard_neg": hard_neg(m)})
        # forward_dep:扇出高的文件 → 正样本是该文件卡片(含"依赖"行)
        for f, _ in fan_out.most_common(12):
            if f in fcards:
                pairs.append({"query": f"在 {repo} 中,{f} 直接依赖(import)了哪些项目内模块?请列全。",
                              "positive": fcards[f], "hard_neg": hard_neg(f)})
        # inheritance:跨文件继承 → 正样本是子类的类卡片
        cls_set = {(c.name, c.file) for c in g.classes}
        inh = 0
        for c in g.classes:
            bases = [b for b in c.bases if (rr := g.resolve_symbol(c.file, b)) and rr[1]
                     and (rr[0], rr[1]) in cls_set and rr[1] != c.file]
            if not bases or (c.name, c.file) not in ccards:
                continue
            pairs.append({"query": f"在 {repo} 中,类 {c.name} 继承自哪个文件里的哪个类?",
                          "positive": ccards[(c.name, c.file)], "hard_neg": hard_neg(c.file)})
            inh += 1
            if inh >= 12:
                break
        # symbol_location:类定义在哪个文件 → 正样本是类卡片
        for c in random.sample(g.classes, min(12, len(g.classes))):
            if (c.name, c.file) in ccards:
                pairs.append({"query": f"在 {repo} 中,类 {c.name} 定义在哪个文件里?",
                              "positive": ccards[(c.name, c.file)], "hard_neg": hard_neg(c.file)})
        print(f"  {repo}: +{len(pairs)-n0} 对")

    random.shuffle(pairs)
    out = PROJECT_ROOT / "data" / "retriever_train.jsonl"
    with open(out, "w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"\n共 {len(pairs)} 个 (查询,正卡片,难负) 三元组 -> {out}")
    print(f"训练项目:{TRAIN_REPOS};留出:{HOLDOUT}(零参与)")


if __name__ == "__main__":
    main()
