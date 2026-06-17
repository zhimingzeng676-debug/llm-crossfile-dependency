"""BM25 词法检索(第二阶段新增,自己实现,约 60 行核心逻辑)。

为什么需要它:向量检索(哪怕真语义模型)对**精确标识符**不一定最强 ——
问 "MAX_AMOUNT_CENTS 是多少" 时,包含这个词本身的块就该赢,
这正是词法(关键词)检索的主场。工业界标配做法是"混合检索":
BM25 管词面精确命中,向量管语义泛化,两路结果融合。

为什么自己实现而不是装 rank_bm25:核心公式就十几行,自己写一遍
(a)免一个网络依赖,(b)比调库学得透 —— 这是教学项目,过程即产出。

BM25 公式(Okapi 版本),对查询里的每个词 t,文档 d 的得分累加:

    IDF(t) * TF(t,d) * (k1+1) / (TF(t,d) + k1 * (1 - b + b * |d|/avgdl))

直觉拆解:
- IDF:词越稀有越有区分度("MAX_AMOUNT_CENTS" >> "payment")
- TF 饱和:词出现 10 次不比 5 次重要一倍(k1 控制饱和速度)
- 长度归一:长文档天然包含更多词,按文档长度折价(b 控制力度)

分词复用 embedding.tokenize(中文 2-gram + 英文标识符拆分),
保证词法和向量两路对"什么算一个词"的理解一致。
"""

from __future__ import annotations

import math
from collections import Counter

from .embedding import tokenize
from .types import Chunk


class BM25Index:
    """对一批 Chunk 建 BM25 倒排索引。k1/b 用业界默认值,不值得消融(数据太小)。"""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        # 每个文档的词频表与长度
        self.doc_tfs: list[Counter] = [Counter(tokenize(c.text)) for c in chunks]
        self.doc_lens = [sum(tf.values()) for tf in self.doc_tfs]
        self.avgdl = (sum(self.doc_lens) / len(self.doc_lens)) if chunks else 1.0
        # 文档频率 -> IDF(+0.5 平滑,max(0) 防负值)
        df: Counter = Counter()
        for tf in self.doc_tfs:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {
            t: max(0.0, math.log((n - d + 0.5) / (d + 0.5) + 1.0)) for t, d in df.items()
        }

    def search(self, query: str, top_n: int = 10) -> list[tuple[int, float]]:
        """返回 [(chunk 下标, BM25 分)],按分降序,只含分>0 的。"""
        q_tokens = tokenize(query)
        scores = [0.0] * len(self.chunks)
        for t in q_tokens:
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.doc_tfs):
                f = tf.get(t, 0)
                if f == 0:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_lens[i] / self.avgdl)
                scores[i] += idf * f * (self.k1 + 1) / denom
        ranked = sorted(
            ((i, s) for i, s in enumerate(scores) if s > 0), key=lambda x: x[1], reverse=True
        )
        return ranked[:top_n]
