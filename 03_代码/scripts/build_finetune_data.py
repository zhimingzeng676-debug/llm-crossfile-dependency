"""构建 QLoRA 微调数据(≥500 条),从 flask/click/jinja2 程序化导出依赖问答对。

红线:**训练只用 flask/click/jinja2,werkzeug 整个留作测试集**——零实体重叠,
最干净的隔离,且顺带验证微调能否泛化(在别的项目学的格式/推理迁到 werkzeug)。

每条样本(chat 格式):
  user   = PE 风格 system + 检索上下文(相关依赖卡片 + 几张干扰卡片) + 问题
  assistant = 结构化标准答案(PE 教的格式:列全、文件—符号—关系、别名还原)
答案由 tree-sitter 静态依赖图导出,可追溯可核验(沿用 56 用例的构造法)。

用法:python scripts/build_finetune_data.py
输出:data/finetune_train.jsonl + data/finetune_val.jsonl(9:1)+ 打印分布。
"""

import collections
import json
import random

from _common import PROJECT_ROOT
from repomind_lab.repo_parser import parse_repo

PROJECTS = ["flask", "click", "jinja2", "requests"]
SYSTEM = (
    "你是代码库跨文件依赖分析专家。只依据提供的[依赖图卡片]作答,不臆测、不编造;"
    "上下文没有的就说\"提供的信息中未包含\";输出结构化:每条关系写「文件 — 符号 — 关系」,"
    "\"列出多个\"的问题逐条列全;遇到别名先还原成真实模块/类。"
)
random.seed(20260613)  # 固定随机,可复现(Date/random 在脚本里不可用,这里是普通 python 进程)


def file_card_text(file, deps, users, classes_in):
    return (f"[依赖图卡片] 文件 {file}\n"
            f"它依赖(import)的仓库内文件: {', '.join(sorted(deps)) or '(无)'}\n"
            f"它被这些文件依赖/使用(import 它的使用方): {', '.join(sorted(users)) or '(无)'}\n"
            f"文件内定义的类: {', '.join(classes_in) or '(无)'}")


def class_card_text(name, file, line, bases_str, kids):
    return (f"[依赖图卡片] 类 {name}\n定义位置: {file} 第 {line} 行\n"
            f"它继承自: {bases_str or '(无基类)'}\n"
            f"继承它的子类: {', '.join(kids) or '(没有仓库内子类)'}")


def build_for_project(proj):
    g = parse_repo(PROJECT_ROOT / "repos" / proj)
    edges = g.import_edges()
    deps_of, importers_of = collections.defaultdict(set), collections.defaultdict(set)
    for a, b in edges:
        deps_of[a].add(b); importers_of[b].add(a)
    cls_set = {(c.name, c.file) for c in g.classes}
    classes_in = collections.defaultdict(list)
    for c in g.classes:
        classes_in[c.file].append(c.name)
    # 子类(别名解析)
    subs = collections.defaultdict(list)
    for c in g.classes:
        for bnm in c.bases:
            rn, rf = g.resolve_symbol(c.file, bnm)
            if rf and (rn, rf) in cls_set and (rn, rf) != (c.name, c.file):
                subs[(rn, rf)].append(f"{c.name} [{c.file}]")

    # 预备各文件/类卡片文本(当上下文 + 干扰）
    file_cards = {f: file_card_text(f, deps_of.get(f, set()), importers_of.get(f, set()), classes_in.get(f, []))
                  for f in g.files}
    class_cards = {}
    for c in g.classes:
        bstr = []
        for bnm in c.bases:
            rn, rf = g.resolve_symbol(c.file, bnm)
            bstr.append(f"{rn} [{rf}]" if rf and (rn, rf) in cls_set else bnm)
        class_cards[(c.name, c.file)] = class_card_text(c.name, c.file, c.start_line, ", ".join(bstr),
                                                        subs.get((c.name, c.file), []))
    all_cards = list(file_cards.values()) + list(class_cards.values())

    samples = []

    def ctx(main_card):
        distract = random.sample(all_cards, min(3, len(all_cards)))
        cards = [main_card] + [d for d in distract if d != main_card]
        random.shuffle(cards)
        return "\n\n".join(cards)

    def add(main_card, q, gold):
        user = f"{SYSTEM}\n\n请根据以下依赖图卡片回答问题。\n\n{ctx(main_card)}\n\n[问题] {q}"
        samples.append({"messages": [{"role": "user", "content": user},
                                     {"role": "assistant", "content": gold}]})

    # forward_dep
    for f in g.files:
        deps = sorted(deps_of.get(f, set()))
        if not deps:
            continue
        gold = f"{f} 直接依赖以下项目内模块:\n" + "\n".join(f"{i}. {d} — import" for i, d in enumerate(deps, 1))
        add(file_cards[f], f"在该项目中,{f} 直接依赖(import)了哪些项目内模块?请列全。", gold)
    # reverse_dep
    for f in g.files:
        users = sorted(importers_of.get(f, set()))
        if not users:
            continue
        gold = f"以下文件依赖(import)了 {f}:\n" + "\n".join(f"{i}. {u}" for i, u in enumerate(users, 1))
        add(file_cards[f], f"在该项目中,哪些文件 import(依赖)了 {f}?请尽量列全。", gold)
    # inheritance(子类继承自谁)
    for c in g.classes:
        bstr = []
        for bnm in c.bases:
            rn, rf = g.resolve_symbol(c.file, bnm)
            if rf and (rn, rf) in cls_set and rf != c.file:
                bstr.append((rn, rf))
        if not bstr:
            continue
        rn, rf = bstr[0]
        gold = f"{c.name} 继承自 {rf} 的 {rn} 类(关系:跨文件继承)。"
        add(class_cards[(c.name, c.file)], f"在该项目中,类 {c.name} 继承自哪个文件里的哪个类?", gold)
    # subclasses(谁继承了 B)
    for (bn, bf), kids in subs.items():
        if len(kids) < 1:
            continue
        names = [k.split(" [")[0] for k in kids]
        gold = f"以下类继承了 {bn}:\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
        add(class_cards.get((bn, bf), file_cards.get(bf, "")), f"在该项目中,哪些类继承了 {bn}?", gold)
    # symbol_location —— 易类型,限额(每项目随机 ~30),避免淹没难类型
    sclasses = list(g.classes)
    random.shuffle(sclasses)
    for c in sclasses[:40]:
        gold = f"{c.name} 定义于 {c.file}。"
        add(class_cards[(c.name, c.file)], f"在该项目中,类 {c.name} 定义在哪个文件里?", gold)
    # indirect_dep(多跳 A->B->C,A 不直接依赖 C)——doc 要求多放的难类型,每文件最多 3 条
    for a in g.files:
        a_deps = deps_of.get(a, set())
        cnt = 0
        for b in sorted(a_deps):
            for c in sorted(deps_of.get(b, set())):
                if c != a and c not in a_deps:
                    gold = (f"是,{a} 间接依赖 {c}:{a} 直接 import 了中间文件 {b},"
                            f"而 {b} 直接 import 了 {c}。中间文件是 {b}。")
                    add(file_cards[a], f"在该项目中,{a} 是否间接依赖 {c}?经过哪个中间文件?", gold)
                    cnt += 1
                    break  # 同一中间文件 b 只取一条
            if cnt >= 3:
                break

    return samples


def main():
    by_proj = {}
    all_samples = []
    for p in PROJECTS:
        s = build_for_project(p)
        by_proj[p] = len(s)
        all_samples.extend(s)
    random.shuffle(all_samples)

    # 9:1 划 train/val
    n_val = max(40, len(all_samples) // 10)
    val, train = all_samples[:n_val], all_samples[n_val:]
    (PROJECT_ROOT / "data" / "finetune_train.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in train), encoding="utf-8")
    (PROJECT_ROOT / "data" / "finetune_val.jsonl").write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in val), encoding="utf-8")
    print(f"总样本 {len(all_samples)}(按项目 {by_proj})")
    print(f"train {len(train)}  val {len(val)}")


if __name__ == "__main__":
    main()
