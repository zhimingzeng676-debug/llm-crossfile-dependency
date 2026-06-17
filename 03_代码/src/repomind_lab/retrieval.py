"""检索后端抽象 —— 本项目最重要的接口(任务书点名要求)。

上层(pipeline / 评测)只认识 RetrievalBackend 这个接口:
"给一个问题字符串,还我 top-k 个相关文本块"。

至于背后是【本地 FAISS】还是【腾讯内网的 RepoMind】,上层完全不关心。
这意味着进了腾讯、拿到 RepoMind 权限后:
  1. 只需实现 RepoMindBackend.retrieve(把 HTTP 调用结果转成 RetrievedChunk)
  2. 配置文件 backend.type 改一个词
  3. **今晚写的整套评测框架、消融实验、测试集原封不动直接复用** ——
     这正是今晚搭脚手架的核心价值。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .embedding import Embedder, tokenize
from .lexical import BM25Index
from .types import RetrievedChunk
from .vector_store import VectorStore


class RetrievalBackend(ABC):
    """检索后端接口。"""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        """返回与 query 最相关的 top_k 个块,按相关度降序。"""


class LocalRagBackend(RetrievalBackend):
    """本地 RAG 实现:Embedder 编码查询 -> VectorStore 找近邻。

    组合(而非继承)Embedder 和 VectorStore:两者各自独立可换,
    检索逻辑本身只有"编码、查询、包装结果"三步。
    """

    def __init__(self, embedder: Embedder, store: VectorStore):
        self.embedder = embedder
        self.store = store

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        query_vec = self.embedder.embed([query])[0]
        hits = self.store.search(query_vec, top_k)
        return [RetrievedChunk(chunk=c, score=s) for c, s in hits]


class HybridBackend(RetrievalBackend):
    """混合检索(第二阶段新增):向量 + BM25 两路召回,RRF 融合。

    融合用 RRF(Reciprocal Rank Fusion):每路只贡献**排名**不贡献原始分,
    final(d) = Σ weight / (60 + rank(d))。
    为什么选 RRF 而不是分数加权:向量相似度(0~1)和 BM25 分(0~20+)
    量纲完全不同,直接加权要先归一化、还对分布形状敏感;RRF 只看排名,
    天然免疫量纲问题,是搜索引擎界的老牌稳健做法(60 是论文默认常数)。

    两路各取 fetch_n(>top_k)个候选再融合 —— 给"一路排前另一路排后"的
    文档留出翻盘空间;只取 top_k 融合的话 RRF 基本退化成"取交集"。
    """

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        vector_weight: float = 1.0,
        bm25_weight: float = 1.0,
        rrf_k: int = 60,
    ):
        self.embedder = embedder
        self.store = store
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k
        # BM25 索引在内存现建:语料就是向量库里的同一批块,保证两路看到同样的世界
        self.bm25 = BM25Index(store.chunks)

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        fetch_n = max(10, top_k * 3)

        query_vec = self.embedder.embed([query])[0]
        vec_hits = self.store.search(query_vec, fetch_n)          # [(Chunk, score)]
        bm25_hits = self.bm25.search(query, fetch_n)              # [(idx, score)]

        fused: dict[str, float] = {}
        by_id = {}
        for rank, (chunk, _) in enumerate(vec_hits):
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + self.vector_weight / (self.rrf_k + rank + 1)
            by_id[chunk.chunk_id] = chunk
        for rank, (idx, _) in enumerate(bm25_hits):
            chunk = self.store.chunks[idx]
            fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + self.bm25_weight / (self.rrf_k + rank + 1)
            by_id[chunk.chunk_id] = chunk

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [RetrievedChunk(chunk=by_id[cid], score=score) for cid, score in ranked]


class RerankingBackend(RetrievalBackend):
    """重排序装饰器(第二阶段新增):包住任意检索后端,先多召回再精排截断。

    思路:召回阶段求"别漏"(取 candidates 个,比如 10),
    重排阶段求"排得准"(用更贵但更准的打分把真正相关的提到前面),
    最后只留 top_k 进 prompt。这是工业 RAG 的标准两段式结构。

    精排打分器可换(scorer 参数),三代尺子对应三个实验:
    - "lexical":词重合启发式(E5:负优化 —— 尺子比第一段检索还钝);
    - "embedder":语义余弦(E9:仍负 —— bge 双塔就是第一段的一路,
      重排=独裁,破坏融合保住的结果多样性);
    - "cross_encoder":交叉编码器(E11,第四阶段兑现)—— 把"查询+候选块"
      **拼成一条输入**过模型,注意力在两段文本之间交互,这是双塔
      (各自独立编码)原理上做不到的,因此它带的是融合各路都没有的新信息。
      代价:每个候选都要过一遍模型,只能用在"少量候选精排"的位置 ——
      这正是两段式架构存在的理由。
    """

    def __init__(self, base: RetrievalBackend, candidates: int = 10,
                 scorer: str = "lexical", embedder: Embedder | None = None,
                 cross_encoder_path: str = ""):
        self.base = base
        self.candidates = candidates
        self.scorer = scorer
        self.embedder = embedder
        if scorer == "embedder" and embedder is None:
            raise ValueError("rerank_scorer: embedder 需要传入 Embedder 实例")
        if scorer == "cross_encoder":
            if not cross_encoder_path:
                raise ValueError("rerank_scorer: cross_encoder 需要在配置里给 rerank_model(模型目录)")
            from sentence_transformers import CrossEncoder

            self.cross_encoder = CrossEncoder(cross_encoder_path)

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        cands = self.base.retrieve(query, top_k=max(self.candidates, top_k))
        if self.scorer == "cross_encoder":
            scores = self.cross_encoder.predict([(query, rc.chunk.text) for rc in cands])
            rescored = [
                RetrievedChunk(chunk=rc.chunk, score=float(scores[i]))
                for i, rc in enumerate(cands)
            ]
        elif self.scorer == "embedder":
            # 语义余弦:向量已 L2 归一化,点积即余弦
            q_vec = self.embedder.embed([query])[0]
            c_vecs = self.embedder.embed([rc.chunk.text for rc in cands])
            rescored = [
                RetrievedChunk(chunk=rc.chunk, score=float(q_vec @ c_vecs[i]))
                for i, rc in enumerate(cands)
            ]
        else:
            q_tokens = set(tokenize(query))
            rescored = []
            for rc in cands:
                c_tokens = tokenize(rc.chunk.text)
                overlap = len(q_tokens & set(c_tokens))
                score = overlap / (len(c_tokens) ** 0.5 + 1)
                rescored.append(RetrievedChunk(chunk=rc.chunk, score=score))
        rescored.sort(key=lambda rc: rc.score, reverse=True)
        return rescored[:top_k]


class FusionBackend(RetrievalBackend):
    """M11:把检索结果按 chunk.kind 分槽 —— 依赖图卡片(graph)vs 相似代码(function/code)。

    动机(arXiv 2505.15179):代码任务上"相似度检索"(检索用法相似的代码)的收益可能
    被本项目偏重的"依赖图卡片"轻视了。本后端把两类信号显式分配槽位,做对照:
    - 纯依赖(n_dep=k, n_sim=0):只给依赖卡片;
    - 纯相似度(n_dep=0, n_sim=k):只给语义相似的代码块(= 文献说的 similarity retrieval);
    - 融合(n_dep + n_sim = k):两者按比例混合,卡片在前(结构先行)、相似代码在后。

    包在已有检索/重排之外(装饰器):先让 base 多召回精排出一个候选池,再按 kind 取槽。
    依赖卡片 kind=="graph";相似代码 kind in {function, code}。去重按 source+chunk_id。
    """

    def __init__(self, base: RetrievalBackend, n_dep: int, n_sim: int):
        self.base = base
        self.n_dep = max(0, n_dep)
        self.n_sim = max(0, n_sim)

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        want = self.n_dep + self.n_sim
        # 多召回:保证两类各有足够候选可选(NL 依赖问句下相似代码块在候选池里偏少,
        # 故取较深的池子,给相似度检索"填满槽位"的公平机会)
        fetch = max(top_k, want, 8) * 10
        cands = self.base.retrieve(query, top_k=fetch)
        dep, sim, seen = [], [], set()
        for rc in cands:
            key = (rc.chunk.source, rc.chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            if rc.chunk.kind == "graph":
                dep.append(rc)
            else:
                sim.append(rc)
        return dep[: self.n_dep] + sim[: self.n_sim]


class NoRetrievalBackend(RetrievalBackend):
    """空检索:始终返回 []。用于"纯 LLM 无 RAG"对照(M3-B E18)——
    prompt 里没有任何代码上下文,只考模型自身的参数化知识。"""

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        return []


class RepoMindBackend(RetrievalBackend):
    """RepoMind 占位实现(拿到内网权限后填充)。

    预期对接方式(进腾讯后按实际 API 调整):
        resp = http_post(RepoMind检索接口, {"query": query, "repo": ..., "top_k": top_k})
        把 resp 里的每条结果转成 RetrievedChunk(chunk_id/source/text/score)

    现在调用会直接抛错并给出指引,而不是悄悄返回空结果 ——
    宁可早炸,不要让评测在静默错误上跑出误导性的分数。
    """

    def __init__(self, endpoint: str = ""):
        self.endpoint = endpoint

    def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedChunk]:
        raise NotImplementedError(
            "RepoMindBackend 是占位实现。拿到内网 API 后,在这里实现 HTTP 调用并把"
            "返回结果映射为 RetrievedChunk;在那之前请用 backend.type: local_rag。"
        )
