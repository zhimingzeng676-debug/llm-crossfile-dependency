"""切块(chunking):把仓库变成一批可被检索的文本块。

为什么要切块:embedding 模型和检索都工作在"一段文本"粒度上。
整个文件太大(检索粒度粗、prompt 塞不下),单行太碎(语义不完整),
所以要切成不大不小的块。**块怎么切直接影响检索质量**,
这正是消融实验最值得做的变量之一,因此这里实现了两种策略:

1. fixed  — 固定行数滑动窗口:简单通用,不依赖语言语法;
            块与块之间留 overlap(重叠行),避免一个函数恰好被从中间切断后,
            两半都检索不到的"边界效应"。
2. function — 用 tree-sitter 按函数边界切:每个函数天然是一个语义完整的单元,
            对"这个函数干嘛/调用了谁"类问题理论上更准。函数体之外的代码
            (模块级常量、import)聚合成一个"模块头"块,保证不丢信息。

另外 load_commit_chunks 把伪造的提交历史也变成块,
让"历史追踪"类问题(谁改的/为什么改)也能走同一条 RAG 链路。
"""

from __future__ import annotations

import json
from pathlib import Path

from .repo_parser import parse_repo
from .types import Chunk

# 默认只索引这些扩展名;README 等文档也值得索引(语义检索常命中文档)
DEFAULT_EXTENSIONS = (".py", ".md")


def _iter_repo_files(repo_root: Path, extensions=DEFAULT_EXTENSIONS):
    """遍历仓库内所有待索引文件,返回 (绝对路径, 相对路径) 对。"""
    for path in sorted(repo_root.rglob("*")):
        if path.is_file() and path.suffix in extensions:
            yield path, path.relative_to(repo_root).as_posix()


def chunk_fixed(repo_root: str | Path, chunk_lines: int = 40, overlap: int = 10) -> list[Chunk]:
    """策略 1:固定行数滑动窗口。

    每 chunk_lines 行一块,相邻块重叠 overlap 行。
    步长 = chunk_lines - overlap,必须为正(配置层会校验)。
    """
    assert 0 <= overlap < chunk_lines, "overlap 必须小于 chunk_lines"
    repo_root = Path(repo_root)
    chunks: list[Chunk] = []
    step = chunk_lines - overlap
    for path, rel in _iter_repo_files(repo_root):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            continue
        start = 0
        while start < len(lines):
            end = min(start + chunk_lines, len(lines))
            text = "\n".join(lines[start:end]).strip()
            if text:  # 跳过纯空白块
                chunks.append(
                    Chunk(
                        chunk_id=f"{rel}#L{start + 1}-{end}",
                        source=rel,
                        text=text,
                        start_line=start + 1,
                        end_line=end,
                        kind="code",
                    )
                )
            if end == len(lines):
                break
            start += step
    return chunks


def chunk_by_function(repo_root: str | Path) -> list[Chunk]:
    """策略 2:tree-sitter 按函数切块(.py),其余文件退回固定切块。

    - 每个函数一个块,文本前面拼上 "文件: xxx" 头,让 embedding 里带上
      文件路径信息(问"在哪个文件"时路径本身就是关键证据)。
    - 函数之外的剩余行(import、模块级常量、模块 docstring)合成一个
      "模块头"块 —— 比如 fees.py 的费率表 FEE_RATES 就在函数体外,丢了它
      "费率在哪配置"这类问题就检索不到了。
    - .md 等非 Python 文件依然用固定切块兜底。
    """
    repo_root = Path(repo_root)
    graph = parse_repo(repo_root)
    chunks: list[Chunk] = []

    # 记录每个文件中已被函数覆盖的行号,剩下的行归入"模块头"块
    covered: dict[str, set[int]] = {}
    for fn in graph.functions:
        chunks.append(
            Chunk(
                chunk_id=f"{fn.file}::{fn.name}",
                source=fn.file,
                text=f"文件: {fn.file}\n函数: {fn.name}\n{fn.code}",
                start_line=fn.start_line,
                end_line=fn.end_line,
                kind="function",
                meta={"function": fn.name, "calls": fn.calls},
            )
        )
        covered.setdefault(fn.file, set()).update(range(fn.start_line, fn.end_line + 1))

    for path, rel in _iter_repo_files(repo_root, extensions=(".py",)):
        lines = path.read_text(encoding="utf-8").splitlines()
        rest = [
            line
            for i, line in enumerate(lines, start=1)
            if i not in covered.get(rel, set())
        ]
        text = "\n".join(rest).strip()
        if text:
            chunks.append(
                Chunk(
                    chunk_id=f"{rel}::<module>",
                    source=rel,
                    text=f"文件: {rel}\n(模块级代码:import、常量、配置)\n{text}",
                    start_line=1,
                    end_line=len(lines),
                    kind="code",
                )
            )

    # 非 .py 文件(README 等)用固定切块补上
    for path, rel in _iter_repo_files(repo_root):
        if path.suffix == ".py":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        text = "\n".join(lines).strip()
        if text:
            chunks.append(
                Chunk(
                    chunk_id=f"{rel}#L1-{len(lines)}",
                    source=rel,
                    text=text,
                    start_line=1,
                    end_line=len(lines),
                    kind="code",
                )
            )
    return chunks


def load_commit_chunks(commits_path: str | Path) -> list[Chunk]:
    """把 jsonl 格式的提交历史变成块(每条 commit 一块)。

    文本里把作者/日期/说明/改动文件拼成自然语句,
    这样"谁修改了手续费逻辑"这类中文问题能和 commit message 产生词面重合。
    """
    chunks: list[Chunk] = []
    path = Path(commits_path)
    if not path.exists():
        return chunks
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        text = (
            f"提交 {c['hash']} 作者: {c['author']} 日期: {c['date']}\n"
            f"提交说明: {c['message']}\n"
            f"改动文件: {', '.join(c['files'])}"
        )
        chunks.append(
            Chunk(
                chunk_id=f"commit:{c['hash']}",
                source=f"commit:{c['hash']}",
                text=text,
                kind="commit",
                meta={"author": c["author"], "date": c["date"], "files": c["files"]},
            )
        )
    return chunks


def load_graph_chunks(repo_root: str | Path) -> list[Chunk]:
    """把调用图**文本化**成"图卡片"块(GraphRAG 思路的简化版,第二阶段新增)。

    动机:纯文本检索对**反向查询**("luhn_check 被谁调用?""models.py 被哪些模块
    使用?")是结构性盲区 —— 答案分散在调用方的代码里,与问题几乎零词面重合,
    评测里 CC-03/CF-03 长期全 0 分。而 tree-sitter 早就解析出了这些反向边,
    只是检索用不上。

    做法:把结构化的图谱"翻译"回自然语言文档 —— 每个函数一张卡片(定义在哪、
    调用谁、**被谁调用**)、每个文件一张卡片(import 谁、**被谁 import**),
    和代码块一起进索引。反向关系从此变成可被检索命中的文字,
    检索器、LLM、评测全都不用改。

    细节:卡片里的函数名后面用 [文件] 而不是 (文件) 标注 ——
    MockLLM 的调用提取模式靠 `名字(` 识别调用语句,圆括号会被误判。
    """
    graph = parse_repo(repo_root)
    chunks: list[Chunk] = []

    callers: dict[str, list[str]] = {}  # 函数名 -> 调用它的 "函数 [文件]" 列表
    for a, b in graph.call_edges():
        caller_file = next((f.file for f in graph.functions if f.name == a), "?")
        callers.setdefault(b, []).append(f"{a} [{caller_file}]")

    known = {f.name for f in graph.functions}
    for fn in graph.functions:
        internal = [c for c in fn.calls if c in known and c != fn.name]
        called_by = callers.get(fn.name, [])
        text = (
            f"[调用图卡片] 函数 {fn.name}\n"
            f"定义位置: {fn.file} 第 {fn.start_line}-{fn.end_line} 行\n"
            f"它调用的仓库内函数: {', '.join(internal) if internal else '(无)'}\n"
            f"它被这些函数调用: {', '.join(called_by) if called_by else '(没有仓库内调用方)'}"
        )
        chunks.append(
            Chunk(
                chunk_id=f"graph:func:{fn.name}",
                source=fn.file,  # source 用所在文件,评测的 expected_sources 按文件写即可
                text=text,
                start_line=fn.start_line,
                end_line=fn.end_line,
                kind="graph",
                meta={"function": fn.name},
            )
        )

    # 用解析后的 import 边(文件→文件)而非原始字符串,卡片才直接对齐"跨文件依赖"问题
    imports_resolved: dict[str, list[str]] = {}  # 文件 -> 它依赖的仓库内文件
    imported_by: dict[str, list[str]] = {}       # 文件 -> import 它的文件列表
    for importer, imported in graph.import_edges():
        imports_resolved.setdefault(importer, []).append(imported)
        imported_by.setdefault(imported, []).append(importer)

    all_files = set(graph.files) or set(graph.imports) | set(imported_by)
    classes_in: dict[str, list[str]] = {}
    for c in graph.classes:
        classes_in.setdefault(c.file, []).append(c.name)

    for file in sorted(all_files):
        deps = sorted(set(imports_resolved.get(file, [])))
        users = sorted(set(imported_by.get(file, [])))
        funcs = [f.name for f in graph.functions if f.file == file]
        text = (
            f"[依赖图卡片] 文件 {file}\n"
            f"它依赖(import)的仓库内文件: {', '.join(deps) if deps else '(无)'}\n"
            f"它被这些文件依赖/使用(import 它的使用方): {', '.join(users) if users else '(没有仓库内使用方)'}\n"
            f"文件内定义的类: {', '.join(classes_in.get(file, [])) or '(无)'}\n"
            f"文件内定义的函数: {', '.join(funcs[:30]) or '(无)'}"
        )
        chunks.append(Chunk(chunk_id=f"graph:file:{file}", source=file, text=text, kind="graph"))

    # 类卡片(M1-2 新增):跨文件继承问题靠它回答。
    # M3-A:基类经 resolve_symbol **别名解析** —— 把 `_SansIORequest` 还原成
    # 真实类 `Request [sansio/request.py]`,攻克 INH-07 符号失联瓶颈。
    cls_set = {(c.name, c.file) for c in graph.classes}
    subclasses: dict[tuple, list[str]] = {}  # (基类名, 基类文件) -> 子类 "名 [文件]"
    for c in graph.classes:
        for b in c.bases:
            rn, rf = graph.resolve_symbol(c.file, b)
            if rf and (rn, rf) in cls_set and (rn, rf) != (c.name, c.file):
                subclasses.setdefault((rn, rf), []).append(f"{c.name} [{c.file}]")
    for c in graph.classes:
        # 基类别名解析后再判是否仓库内类
        base_strs = []
        has_repo_base = False
        for b in c.bases:
            rn, rf = graph.resolve_symbol(c.file, b)
            if rf and (rn, rf) in cls_set:
                base_strs.append(f"{rn} [{rf}]")
                has_repo_base = True
            else:
                base_strs.append(b)  # 外部基类(Exception/Protocol)或解析不到
        kids = subclasses.get((c.name, c.file), [])
        # M3-A:为**每个类**发卡片。类卡片是"X 定义在哪个文件 / 继承自谁"的天然
        # 检索单元,对真实项目的 symbol_location(LOC)和 inheritance 用例都必需。
        # (M1-2 曾为避免 mock 反向 import 用例的同源稀释而跳过无继承的类,
        #  但那是为一个 frozen 测试集丢真实能力 —— 另一种过拟合。这里改回全发,
        #  mock 的轻微同源竞争如实记录,见 EXPERIMENTS E17。)
        text = (
            f"[依赖图卡片] 类 {c.name}\n"
            f"定义位置: {c.file} 第 {c.start_line}-{c.end_line} 行\n"
            f"它继承自: {', '.join(base_strs) if base_strs else '(无基类)'}\n"
            f"继承它的子类: {', '.join(kids) if kids else '(没有仓库内子类)'}"
        )
        chunks.append(
            Chunk(chunk_id=f"graph:class:{c.file}:{c.name}", source=c.file, text=text, kind="graph",
                  meta={"class": c.name})
        )
    return chunks


def load_constant_cards(repo_root: str | Path) -> list[Chunk]:
    """把模块级常量做成"常量卡"(第四阶段 E12,修 ERROR_ANALYSIS 的 B 类失分)。

    动机:function 切块下,常量挤在"模块头"大块里检索竞争力弱,
    SE-04(大额阈值)/CF-05(优惠券上限)因此失分 —— 检索命中了文件,
    却没命中含答案的块。每个常量一张卡(名字 + 紧邻注释 + 完整赋值语句),
    粒度恰好对齐"XXX 的值是多少"这类问题。

    注意:卡片**如实保留**常量上方的注释 —— 包括 coupons.py 那条故意过时的
    注释("最高抵扣 50 元"vs 代码 3000)。修检索不等于替 LLM 消化矛盾,
    "信注释还是信代码"留给生成侧(真 LLM 接入后的考点,见 E7)。
    """
    graph = parse_repo(repo_root)
    chunks: list[Chunk] = []
    for c in graph.constants:
        parts = [f"[调用图卡片] 常量 {c.name}", f"定义位置: {c.file} 第 {c.line} 行"]
        if c.comment:
            parts.append(f"注释: {c.comment}")
        parts.append(f"定义: {c.code}")
        chunks.append(
            Chunk(
                chunk_id=f"graph:const:{c.file}:{c.name}",
                source=c.file,
                text="\n".join(parts),
                start_line=c.line,
                end_line=c.line,
                kind="graph",
                meta={"constant": c.name},
            )
        )
    return chunks


def build_chunks(
    repo_root: str | Path,
    strategy: str = "fixed",
    chunk_lines: int = 40,
    overlap: int = 10,
    commits_path: str | Path | None = None,
    include_graph_cards: bool = False,
    include_constant_cards: bool = False,
) -> list[Chunk]:
    """统一入口:按配置选切块策略,可选拼上提交历史块和图/常量卡片。pipeline 只调这一个函数。"""
    if strategy == "fixed":
        chunks = chunk_fixed(repo_root, chunk_lines=chunk_lines, overlap=overlap)
    elif strategy == "function":
        chunks = chunk_by_function(repo_root)
    else:
        raise ValueError(f"未知切块策略: {strategy}(可选 fixed / function)")
    if commits_path:
        chunks.extend(load_commit_chunks(commits_path))
    if include_graph_cards:
        chunks.extend(load_graph_chunks(repo_root))
    if include_constant_cards:
        chunks.extend(load_constant_cards(repo_root))
    return chunks
