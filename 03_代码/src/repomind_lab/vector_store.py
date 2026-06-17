"""向量索引:存一堆向量,支持"给我和查询向量最相似的 top-k 个"。

VectorStore 也是接口。当前用 FAISS 实现(facebook 开源的向量检索库,
工业界标配)。mock 仓库只有几十个块,其实暴力扫描也够快 —— 用 FAISS 的意义
在于:① 练习真实技术栈;② 将来索引十万级块时不用改代码。

索引类型选了 IndexFlatIP(精确内积检索):
- "Flat" = 不做近似,精确算所有距离。数据量小用 Flat 最简单且无精度损失;
  数据量大(百万级)才需要 IVF/HNSW 等近似索引,那是 NEXT_STEPS 的事。
- "IP" = inner product 内积。因为 embedding 已做 L2 归一化,内积 = 余弦相似度。
"""

from __future__ import annotations

import json
import pickle
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path

import faiss
import numpy as np

from .types import Chunk


class VectorStore(ABC):
    """向量存储接口:add 建库,search 查询,save/load 持久化。"""

    @abstractmethod
    def add(self, vectors: np.ndarray, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def search(self, query_vec: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]: ...

    @abstractmethod
    def save(self, dir_path: str | Path) -> None: ...

    @classmethod
    @abstractmethod
    def load(cls, dir_path: str | Path) -> "VectorStore": ...


class FaissVectorStore(VectorStore):
    """FAISS IndexFlatIP 实现。

    FAISS 只存向量,不存文本 —— 块的原文/元数据由本类用平行列表自己保管,
    检索返回的下标再映射回 Chunk。持久化时分两个文件:
    index.faiss(FAISS 原生格式)+ chunks.pkl(Python 对象)。
    """

    def __init__(self, dim: int):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self.chunks: list[Chunk] = []

    def add(self, vectors: np.ndarray, chunks: list[Chunk]) -> None:
        assert vectors.shape[0] == len(chunks), "向量数和块数必须一致"
        assert vectors.shape[1] == self.dim, f"向量维度 {vectors.shape[1]} != 索引维度 {self.dim}"
        self.index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        self.chunks.extend(chunks)

    def search(self, query_vec: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        query = np.ascontiguousarray(query_vec.reshape(1, -1), dtype=np.float32)
        top_k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS 用 -1 填充"没那么多结果"的空位
                continue
            results.append((self.chunks[idx], float(score)))
        return results

    def save(self, dir_path: str | Path) -> None:
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(dir_path / "index.faiss"))
        with open(dir_path / "chunks.pkl", "wb") as f:
            pickle.dump(self.chunks, f)
        # 同时落一份人类可读的清单,方便肉眼检查"索引里到底有什么"
        manifest = {"dim": self.dim, "n_chunks": len(self.chunks),
                    "chunks": [{k: v for k, v in asdict(c).items() if k != "text"} for c in self.chunks]}
        (dir_path / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, dir_path: str | Path) -> "FaissVectorStore":
        dir_path = Path(dir_path)
        index = faiss.read_index(str(dir_path / "index.faiss"))
        with open(dir_path / "chunks.pkl", "rb") as f:
            chunks = pickle.load(f)
        store = cls(dim=index.d)
        store.index = index
        store.chunks = chunks
        return store
