"""Embedding:把文本变成定长向量,使"语义相近"≈"向量距离近"。

设计要点:**Embedder 是接口**,上层(vector_store / retrieval)只依赖接口,
所以换一种 embedding 只需改一行配置,不动任何其他代码。

当前提供两个实现:

1. HashingEmbedder(默认,本地、零联网、确定性)
   原理是经典的"哈希技巧"(hashing trick)词袋向量:
   - 把文本切成 token(英文按单词 + 驼峰/下划线拆分,中文按字符 2-gram)
   - 每个 token 哈希到 [0, dim) 的一个桶,桶计数 +1
   - 向量做 L2 归一化,之后内积 = 余弦相似度
   它**没有语义泛化能力**(不知道"费用"和"手续费"是近义词),本质是
   "带容错的关键词匹配"。但对代码检索这种关键词重合度高的场景是个体面的
   baseline,且让整条链路今晚就能真实跑通。

2. SentenceTransformerEmbedder(占位,需联网下载模型)
   将来网络可用时:pip install sentence-transformers,
   配置 embedder: sentence_transformer 即可切换,接口完全一致。
   这是真正的"语义" embedding,预期对语义检索类问题有明显提升 —— 装好后
   跑一次消融实验即可量化(NEXT_STEPS 里有具体步骤)。
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    """Embedding 接口:输入一批文本,输出 (N, dim) 的 float32 矩阵。"""

    @property
    @abstractmethod
    def dim(self) -> int:
        """向量维度(建索引时要用)。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """批量编码。返回 L2 归一化后的矩阵,保证内积即余弦相似度。"""

    @property
    def name(self) -> str:
        """用于结果记录,让实验报告里能看出用的哪种 embedding。"""
        return type(self).__name__


# 匹配英文标识符;之后再按驼峰/下划线二次拆分
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_CAMEL_RE = re.compile(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])")
# CJK 统一表意文字范围(覆盖常用汉字)
_CJK_RE = re.compile(r"[一-鿿]+")


def tokenize(text: str) -> list[str]:
    """混合中英文的分词:

    - 英文标识符整体保留,**并且**按驼峰/下划线拆开再各算一个 token
      (这样问题里写 "process_payment" 或只写 "payment" 都能命中)
    - 中文连续段切成字符 2-gram("手续费" -> 手续/续费),
      不依赖 jieba 等分词库,对短查询足够稳健
    """
    text = text.lower()
    tokens: list[str] = []
    for m in _WORD_RE.finditer(text):
        word = m.group()
        tokens.append(word)
        parts = [p.lower() for p in _CAMEL_RE.findall(word)]
        if len(parts) > 1:
            tokens.extend(parts)
        elif "_" in word:
            tokens.extend(p for p in word.split("_") if p)
    for m in _CJK_RE.finditer(text):
        seg = m.group()
        if len(seg) == 1:
            tokens.append(seg)
        else:
            tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
    return tokens


class HashingEmbedder(Embedder):
    """哈希词袋向量(详见模块 docstring)。dim 越大哈希冲突越少,512 已够 mock 仓库用。"""

    def __init__(self, dim: int = 512):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _bucket(self, token: str) -> int:
        # 用 md5 而不是内置 hash():内置 hash 每次进程启动加盐,
        # 会导致索引不可复现(今天建的索引明天就查不准了)
        h = hashlib.md5(token.encode("utf-8")).digest()
        return int.from_bytes(h[:4], "little") % self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        mat = np.zeros((len(texts), self._dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in tokenize(text):
                mat[i, self._bucket(tok)] += 1.0
        # L2 归一化;空文本向量保持全零(避免除零)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms


class SentenceTransformerEmbedder(Embedder):
    """真语义 embedding(第二阶段已兑现,不再是占位)。

    model_name 既可以是 HuggingFace 模型 ID,也可以是**本地目录**
    (本项目用 models/bge-small-zh-v1.5,权重是 curl 直下镜像得到的 ——
    huggingface_hub 走 hf-mirror 会被元数据校验拦住,
    完整下载过程记录在 scripts/download_model.py 的 docstring)。
    """

    def __init__(self, model_name: str = "models/bge-small-zh-v1.5"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers 未安装。pip install sentence-transformers "
                "-i https://mirrors.aliyun.com/pypi/simple/,或在配置里改回 embedder.type: hashing"
            ) from e
        self._model = SentenceTransformer(model_name)
        # sentence-transformers 5.x 改了方法名,做个兼容
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self._dim = get_dim()

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True).astype(np.float32)


def create_embedder(type_: str = "hashing", **kwargs) -> Embedder:
    """工厂函数:配置字符串 -> Embedder 实例。新增实现时在这里注册。"""
    if type_ == "hashing":
        return HashingEmbedder(dim=kwargs.get("dim", 512))
    if type_ == "sentence_transformer":
        return SentenceTransformerEmbedder(model_name=kwargs.get("model_name", "models/bge-small-zh-v1.5"))
    raise ValueError(f"未知 embedder 类型: {type_}(可选 hashing / sentence_transformer)")
