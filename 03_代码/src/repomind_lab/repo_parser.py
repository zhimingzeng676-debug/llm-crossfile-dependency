"""用 tree-sitter 解析 Python 代码仓库:函数定义、调用关系、import 依赖。

为什么用 tree-sitter 而不是正则或 Python 自带的 ast 模块:
- tree-sitter 是工业级增量解析器(GitHub 代码导航就用它),**跨语言**:
  今天解析 Python,将来 RepoMind 项目里要解析 C++/Go/Java 时换个语法包就行,
  解析逻辑(walk 语法树)是同一套思路。ast 模块只能解析 Python。
- 它对语法错误容忍度高,解析不完整代码也不会直接崩。

本模块输出三类信息:
1. 函数定义:名字、所在文件、起止行、源码文本(供"按函数切块"复用)
2. 调用边:函数 A 的函数体里调用了名字 B(静态、按名字匹配,见下方"已知局限")
3. import 依赖:每个文件 import 了哪些模块

已知局限(写给将来改进的人):
- 调用关系是"按名字"匹配的,不做类型推断。如果两个文件里有同名函数,
  调用边会有歧义。对 mock 仓库够用;真实仓库需要结合 import 信息消歧(见 NEXT_STEPS)。
- 只处理 .py 文件。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

# 解析器是无状态的,做成模块级单例,避免每个文件都重建一遍
_PY_LANGUAGE = Language(tspython.language())
_PARSER = Parser(_PY_LANGUAGE)


@dataclass
class FunctionInfo:
    """一个函数(或方法)的静态信息。"""

    name: str
    file: str            # 相对仓库根的路径,统一用 / 分隔
    start_line: int      # 1-based,含 def 行
    end_line: int
    code: str            # 完整源码(含 def 行和函数体)
    calls: list[str] = field(default_factory=list)  # 函数体内调用到的名字(去重保序)


@dataclass
class ConstantInfo:
    """一个模块级常量(第四阶段新增,E12 常量盲区修复)。

    背景:function 切块把常量挤进"模块头"块,SE-04/CF-05 因此失分
    (ERROR_ANALYSIS B 类)。把每个常量解析出来做成独立"常量卡"进索引,
    检索就能直接命中"名字 + 值 + 它上面的注释"。
    """

    name: str
    file: str
    line: int            # 1-based
    code: str            # 完整赋值语句(可能多行,如 dict 字面量)
    comment: str = ""    # 紧邻上一行的 # 注释(常量的"为什么"通常写在这)


@dataclass
class ClassInfo:
    """一个类定义(M1-2 新增,用于跨文件继承分析)。

    bases 是基类的"简单名"列表(取 dotted 基类的最后一段),
    如 `class Request(_SansIORequest)` → bases=['_SansIORequest'];
    `class BadRequestKeyError(BadRequest, KeyError)` → ['BadRequest','KeyError']。
    跨文件继承的判定:某个 base 的简单名能匹配到另一个文件里的 ClassInfo.name。
    """

    name: str
    file: str
    start_line: int
    end_line: int
    bases: list[str] = field(default_factory=list)


@dataclass
class RepoGraph:
    """整个仓库的解析结果:文件表 + 函数 + 类 + 调用边 + import 表 + 常量表。"""

    functions: list[FunctionInfo] = field(default_factory=list)
    imports: dict[str, list[str]] = field(default_factory=dict)  # 文件 -> import 的原始模块字符串
    constants: list[ConstantInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    files: list[str] = field(default_factory=list)  # 所有被解析的 .py 相对路径(含无函数的)
    package_name: str = ""  # 若仓库根有 __init__.py,则它本身是个包,名字=根目录名
    # 文件 -> {本地名: (模块字符串 或 None, 原始名)}。M3-A 别名解析:
    #   `from ..sansio.request import Request as _SansIORequest`
    #     -> {_SansIORequest: ("..sansio.request", "Request")}
    #   `from .structures import ImmutableList`(无 as,也记,用于跨文件符号定位)
    #     -> {ImmutableList: (".structures", "ImmutableList")}
    #   模块内别名 `_Foo = Bar` -> {_Foo: (None, "Bar")}
    aliases: dict[str, dict] = field(default_factory=dict)

    def resolve_symbol(self, file: str, name: str) -> tuple[str, str | None]:
        """把 file 里用到的名字 name 沿别名链还原成 (真实名, 定义文件)。

        M3-A 核心:解决"符号物理在场但失联"——base 写作别名 `_SansIORequest`,
        真实类是 sansio/request.py 的 `Request`。沿 import-as / 模块内别名逐跳追,
        直到非别名为止;追到仓库外(标准库)则文件返回 None。
        """
        files = set(self.files)
        cur_file, cur_name = file, name
        seen = set()
        for _ in range(8):
            if (cur_file, cur_name) in seen:
                break
            seen.add((cur_file, cur_name))
            amap = self.aliases.get(cur_file, {})
            if cur_name not in amap:
                break
            module_str, orig = amap[cur_name]
            if module_str is None:  # 同文件别名 X = Y
                if orig == cur_name:
                    break
                cur_name = orig
                continue
            target = _resolve_import(cur_file, module_str, files, self.package_name)
            if target is None:
                return (orig, None)  # 来自仓库外模块
            cur_file, cur_name = target, orig
        return (cur_name, cur_file)

    def callers_of(self, name: str) -> list["FunctionInfo"]:
        """反向查询:哪些函数调用了 name。调用图相比纯文本检索的核心增量就在这里。"""
        return [f for f in self.functions if name in f.calls and f.name != name]

    def importers_of(self, target_file: str) -> list[str]:
        """反向依赖:哪些文件 import 了 target_file。跨文件依赖分析的核心查询。"""
        return sorted({a for a, b in self.import_edges() if b == target_file})

    def import_edges(self) -> list[tuple[str, str]]:
        """展开成 (importer 文件, 被 import 文件) 边列表,只保留指向仓库内文件的边。

        按真实 Python 导入语义解析(M1-2 为接入真实包重写):
        - 相对导入数点号:`.x`=同包,`..x`=父包,逐点上溯;`.sansio.request` 支持多级。
        - 绝对导入若以包名开头(如 werkzeug 自引用 `werkzeug.utils`)先剥包名前缀。
        - 目标既可能是模块文件(x.py)也可能是子包(x/__init__.py),两者都试。
        - 解析不到仓库内文件的(标准库、第三方)直接丢弃。
        """
        files = set(self.files) or ({f.file for f in self.functions} | set(self.imports.keys()))
        edges = []
        seen = set()
        for importer, modules in self.imports.items():
            for m in modules:
                target = _resolve_import(importer, m, files, self.package_name)
                if target and target != importer and (importer, target) not in seen:
                    seen.add((importer, target))
                    edges.append((importer, target))
        return edges

    def class_edges(self) -> list[tuple[str, str]]:
        """继承边 (子类名, 基类名),只保留基类也是仓库内类的(跨文件/同文件均含)。"""
        known = {c.name for c in self.classes}
        edges = []
        for c in self.classes:
            for base in c.bases:
                if base in known and base != c.name:
                    edges.append((c.name, base))
        return edges

    def call_edges(self) -> list[tuple[str, str]]:
        """展开成 (调用方, 被调用方) 边列表,只保留被调用方也是仓库内函数的边。

        过滤掉 print/len 这类内置函数调用,让调用图只反映"项目内部"的结构。
        """
        known = {f.name for f in self.functions}
        edges = []
        for f in self.functions:
            for callee in f.calls:
                if callee in known and callee != f.name:
                    edges.append((f.name, callee))
        return edges

    def to_dict(self) -> dict:
        """序列化成 JSON 友好的 dict(scripts/parse_repo.py 落盘用)。"""
        return {
            "functions": [
                {
                    "name": f.name,
                    "file": f.file,
                    "start_line": f.start_line,
                    "end_line": f.end_line,
                    "calls": f.calls,
                }
                for f in self.functions
            ],
            "call_edges": [{"caller": a, "callee": b} for a, b in self.call_edges()],
            "imports": self.imports,
            "import_edges": [{"importer": a, "imported": b} for a, b in self.import_edges()],
            "classes": [
                {"name": c.name, "file": c.file, "start_line": c.start_line,
                 "end_line": c.end_line, "bases": c.bases}
                for c in self.classes
            ],
            "class_edges": [{"sub": a, "base": b} for a, b in self.class_edges()],
            "constants": [
                {"name": c.name, "file": c.file, "line": c.line, "comment": c.comment}
                for c in self.constants
            ],
        }


def _resolve_import(importer: str, module_str: str, files: set, package_name: str) -> str | None:
    """把一条 import 的模块字符串解析成仓库内文件路径(解析不到返回 None)。

    实现真实 Python 导入语义,见 RepoGraph.import_edges 的 docstring。
    """
    if module_str.startswith("."):
        n_dots = len(module_str) - len(module_str.lstrip("."))
        rest = module_str[n_dots:]
        pkg_parts = importer.split("/")[:-1]  # importer 所在包的路径段
        up = n_dots - 1                        # 1 个点=同包,多出来的每个点上溯一层
        if up > len(pkg_parts):
            return None
        base_parts = pkg_parts[: len(pkg_parts) - up] if up else pkg_parts
        target_parts = base_parts + (rest.split(".") if rest else [])
    else:
        target_parts = module_str.split(".")
        # 包自引用(werkzeug.x):剥掉包名前缀,变成相对仓库根
        if package_name and target_parts and target_parts[0] == package_name:
            target_parts = target_parts[1:]
    if not target_parts:
        return None
    as_module = "/".join(target_parts) + ".py"
    as_package = "/".join(target_parts) + "/__init__.py"
    if as_module in files:
        return as_module
    if as_package in files:
        return as_package
    return None


def _walk(node: Node):
    """深度优先遍历语法树的所有节点(生成器)。"""
    yield node
    for child in node.children:
        yield from _walk(child)


def _collect_calls(body: Node, src: bytes) -> list[str]:
    """收集一个函数体里所有"被调用的名字",去重且保持出现顺序。

    tree-sitter 里函数调用是 call 节点,其 function 子节点可能是:
    - identifier:        直接调用,如 validate_card(...)
    - attribute:         方法/模块调用,如 fees.calculate_fee(...) —— 取最后一段名字
    """
    calls: list[str] = []
    for n in _walk(body):
        if n.type != "call":
            continue
        fn = n.child_by_field_name("function")
        if fn is None:
            continue
        if fn.type == "identifier":
            name = src[fn.start_byte : fn.end_byte].decode("utf-8", "replace")
        elif fn.type == "attribute":
            attr = fn.child_by_field_name("attribute")
            if attr is None:
                continue
            name = src[attr.start_byte : attr.end_byte].decode("utf-8", "replace")
        else:
            continue
        if name not in calls:
            calls.append(name)
    return calls


def _collect_imports(root: Node, src: bytes) -> list[str]:
    """收集一个文件 import 的模块名(import_statement / import_from_statement)。"""
    modules: list[str] = []
    for n in _walk(root):
        if n.type == "import_statement":
            # import a.b, c  ->  取每个 dotted_name
            for child in _walk(n):
                if child.type == "dotted_name":
                    modules.append(src[child.start_byte : child.end_byte].decode("utf-8", "replace"))
        elif n.type == "import_from_statement":
            # from X import y  ->  记模块 X(module_name 字段);相对导入记 "."
            mod = n.child_by_field_name("module_name")
            if mod is not None:
                modules.append(src[mod.start_byte : mod.end_byte].decode("utf-8", "replace"))
    # 去重保序
    seen: list[str] = []
    for m in modules:
        if m not in seen:
            seen.append(m)
    return seen


# 常量命名惯例:全大写(允许前导下划线),如 MAX_AMOUNT_CENTS / _OLD_BLACKLIST
import re as _re

_CONST_NAME_RE = _re.compile(r"^_?[A-Z][A-Z0-9_]*$")


def _collect_constants(root: Node, src: bytes, rel_path: str) -> list["ConstantInfo"]:
    """收集模块级常量:只看 root 的**直接子节点**(函数/类体内的赋值不算),
    赋值左边是全大写命名的才算常量(Python 社区惯例)。"""
    lines = src.decode("utf-8", "replace").splitlines()
    constants: list[ConstantInfo] = []
    for child in root.children:
        if child.type != "expression_statement":
            continue
        for n in child.children:
            if n.type != "assignment":
                continue
            left = n.child_by_field_name("left")
            if left is None or left.type != "identifier":
                continue
            name = src[left.start_byte : left.end_byte].decode("utf-8", "replace")
            if not _CONST_NAME_RE.match(name):
                continue
            row = n.start_point[0]  # 0-based
            # 紧邻上一行如果是 # 注释,一并捕获(常量的"为什么"通常写在那)
            comment = ""
            if row >= 1 and lines[row - 1].strip().startswith("#"):
                comment = lines[row - 1].strip()
            constants.append(
                ConstantInfo(
                    name=name,
                    file=rel_path,
                    line=row + 1,
                    code=src[n.start_byte : n.end_byte].decode("utf-8", "replace"),
                    comment=comment,
                )
            )
    return constants


def _base_simple_name(node: Node, src: bytes) -> str | None:
    """从基类节点取"简单名":identifier 直接取;attribute(如 t.Protocol)取最后一段;
    subscript(如 Generic[T])取被下标的名字。其它(字面量等)忽略。"""
    if node.type == "identifier":
        return src[node.start_byte : node.end_byte].decode("utf-8", "replace")
    if node.type == "attribute":
        attr = node.child_by_field_name("attribute")
        return src[attr.start_byte : attr.end_byte].decode("utf-8", "replace") if attr else None
    if node.type == "subscript":
        val = node.child_by_field_name("value")
        return _base_simple_name(val, src) if val else None
    return None


def _collect_classes(root: Node, src: bytes, rel_path: str) -> list["ClassInfo"]:
    """收集所有类定义(含嵌套),记录名字、行号、基类简单名列表。"""
    classes: list[ClassInfo] = []
    for n in _walk(root):
        if n.type != "class_definition":
            continue
        name_node = n.child_by_field_name("name")
        if name_node is None:
            continue
        bases: list[str] = []
        superclasses = n.child_by_field_name("superclasses")  # argument_list 或 None
        if superclasses is not None:
            for child in superclasses.children:
                if child.type in (",", "(", ")"):
                    continue
                # 跳过关键字参数 metaclass= 之类
                if child.type == "keyword_argument":
                    continue
                bn = _base_simple_name(child, src)
                if bn and bn not in bases:
                    bases.append(bn)
        classes.append(
            ClassInfo(
                name=src[name_node.start_byte : name_node.end_byte].decode("utf-8", "replace"),
                file=rel_path,
                start_line=n.start_point[0] + 1,
                end_line=n.end_point[0] + 1,
                bases=bases,
            )
        )
    return classes


def _last_seg(node: Node, src: bytes) -> str:
    """dotted_name / identifier 取最后一段名字(`a.b.C` -> `C`)。"""
    txt = src[node.start_byte : node.end_byte].decode("utf-8", "replace")
    return txt.rsplit(".", 1)[-1]


def _collect_aliases(root: Node, src: bytes) -> dict:
    """收集本文件的别名/导入符号映射(M3-A)。

    覆盖三种:`from M import A as B`、`from M import A`(无 as 也记,供跨文件符号
    定位)、模块内 `B = A`(纯标识符赋值)。返回 {本地名: (模块字符串 或 None, 原始名)}。
    """
    aliases: dict = {}
    for n in _walk(root):
        if n.type == "import_from_statement":
            mod = n.child_by_field_name("module_name")
            if mod is None:
                continue
            module_str = src[mod.start_byte : mod.end_byte].decode("utf-8", "replace")
            for nm in n.children_by_field_name("name"):
                if nm.type == "aliased_import":
                    name = nm.child_by_field_name("name")
                    alias = nm.child_by_field_name("alias")
                    if name is not None and alias is not None:
                        local = src[alias.start_byte : alias.end_byte].decode("utf-8", "replace")
                        aliases[local] = (module_str, _last_seg(name, src))
                elif nm.type in ("dotted_name", "identifier"):
                    local = _last_seg(nm, src)
                    aliases[local] = (module_str, local)
        elif n.type == "import_statement":
            for nm in n.children_by_field_name("name"):
                if nm.type == "aliased_import":
                    name = nm.child_by_field_name("name")
                    alias = nm.child_by_field_name("alias")
                    if name is not None and alias is not None:
                        local = src[alias.start_byte : alias.end_byte].decode("utf-8", "replace")
                        module_str = src[name.start_byte : name.end_byte].decode("utf-8", "replace")
                        aliases[local] = (module_str, None)
    # 模块内别名赋值 X = Y(左右都是单标识符,root 的直接子句)
    for child in root.children:
        if child.type != "expression_statement":
            continue
        for a in child.children:
            if a.type != "assignment":
                continue
            left = a.child_by_field_name("left")
            right = a.child_by_field_name("right")
            if left is not None and right is not None and left.type == "identifier" and right.type == "identifier":
                ln = src[left.start_byte : left.end_byte].decode("utf-8", "replace")
                rn = src[right.start_byte : right.end_byte].decode("utf-8", "replace")
                if ln != rn:
                    aliases[ln] = (None, rn)
    return aliases


def parse_file(path: Path, rel_path: str) -> tuple[list[FunctionInfo], list[str], list[ConstantInfo], list[ClassInfo], dict]:
    """解析单个 .py 文件,返回 (函数, import 列表, 常量, 类, 别名映射)。"""
    src = path.read_bytes()
    tree = _PARSER.parse(src)
    root = tree.root_node

    functions: list[FunctionInfo] = []
    for n in _walk(root):
        if n.type != "function_definition":
            continue
        name_node = n.child_by_field_name("name")
        body_node = n.child_by_field_name("body")
        if name_node is None or body_node is None:
            continue
        functions.append(
            FunctionInfo(
                name=src[name_node.start_byte : name_node.end_byte].decode("utf-8", "replace"),
                file=rel_path,
                # tree-sitter 的行号是 0-based,转成人类习惯的 1-based
                start_line=n.start_point[0] + 1,
                end_line=n.end_point[0] + 1,
                code=src[n.start_byte : n.end_byte].decode("utf-8", "replace"),
                calls=_collect_calls(body_node, src),
            )
        )
    return (
        functions,
        _collect_imports(root, src),
        _collect_constants(root, src, rel_path),
        _collect_classes(root, src, rel_path),
        _collect_aliases(root, src),
    )


def parse_repo(repo_root: str | Path) -> RepoGraph:
    """解析整个仓库(递归找 .py 文件),返回 RepoGraph。"""
    repo_root = Path(repo_root)
    graph = RepoGraph()
    for path in sorted(repo_root.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        funcs, imports, consts, classes, aliases = parse_file(path, rel)
        graph.files.append(rel)
        graph.functions.extend(funcs)
        graph.constants.extend(consts)
        graph.classes.extend(classes)
        if imports:
            graph.imports[rel] = imports
        if aliases:
            graph.aliases[rel] = aliases
    # 仓库根有 __init__.py → 它本身是个包,名字=根目录名(用于剥离自引用绝对导入前缀)
    if "__init__.py" in graph.files:
        graph.package_name = repo_root.name
    return graph


def save_graph(graph: RepoGraph, out_path: str | Path) -> None:
    """把调用图存成 JSON,给人看也给后续工具(如可视化)用。"""
    Path(out_path).write_text(
        json.dumps(graph.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
