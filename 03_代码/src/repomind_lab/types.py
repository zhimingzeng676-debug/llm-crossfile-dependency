"""全项目共享的基础数据结构。

单独成文件是为了避免循环 import:chunking、retrieval、evalkit 都要用 Chunk,
如果把它定义在其中任何一个模块里,其他模块就得绕着 import。
"""

from dataclasses import dataclass, field


@dataclass
class Chunk:
    """一个被索引的文本块 —— RAG 的最小检索单位。

    既可以来自源代码文件(source 是文件路径),
    也可以来自提交历史(source 形如 "commit:a1f3c92"),
    检索层不区分两者,统一当文本处理。
    """

    chunk_id: str          # 全局唯一,如 "payment/gateway.py#L1-40"
    source: str            # 来源标识(文件路径 或 commit:hash)
    text: str              # 实际被 embedding 的文本内容
    start_line: int = 0    # 在源文件中的起始行(commit 块为 0)
    end_line: int = 0
    kind: str = "code"     # code / function / commit —— 方便统计与过滤
    meta: dict = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """一次检索命中的结果:块 + 相似度分数。"""

    chunk: Chunk
    score: float
