"""把所有模块串成一条链:问题进 → 检索 → 拼 prompt → LLM → 答案出。

这是上层(脚本、评测)使用本库的唯一入口。两个阶段:
- build_index:离线阶段。切块 → embedding → 建 FAISS 索引 → 落盘。
  仓库不变就只需建一次,之后所有提问/评测复用同一份索引。
- RagPipeline.answer:在线阶段。对每个问题做检索 + 生成。

answer 返回的不只是答案文本,还带上检索结果和完整 prompt ——
评测框架要用检索结果算"检索命中率",调试时要看 prompt 长什么样,
所以把中间产物全部透出,而不是只给最终字符串。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .chunking import build_chunks
from .config import ExperimentConfig
from .embedding import Embedder, create_embedder
from .llm import LLM, create_llm
from .prompting import PromptConfig, build_prompt
from .retrieval import (
    FusionBackend,
    HybridBackend,
    LocalRagBackend,
    NoRetrievalBackend,
    RepoMindBackend,
    RerankingBackend,
    RetrievalBackend,
)
from .types import RetrievedChunk
from .vector_store import FaissVectorStore


@dataclass
class PipelineResult:
    """一次问答的完整产物(含中间结果,供评测/调试用)。"""

    question: str
    answer: str
    retrieved: list[RetrievedChunk]
    prompt: str


def _resolve_model_name(model_name: str, root: Path) -> str:
    """embedder.model_name 若是项目内的本地目录(如 models/bge-small-zh-v1.5),
    解析成绝对路径,这样从任何工作目录运行脚本都能找到;否则原样当 HF 模型 ID 用。"""
    local = root / model_name
    return str(local) if local.exists() else model_name


def build_index(cfg: ExperimentConfig, project_root: str | Path = ".") -> dict:
    """离线建索引。返回统计信息(块数等),给脚本打印用。"""
    root = Path(project_root)
    chunks = build_chunks(
        root / cfg.repo_root,
        strategy=cfg.chunking.strategy,
        chunk_lines=cfg.chunking.chunk_lines,
        overlap=cfg.chunking.overlap,
        commits_path=(root / cfg.commits_path) if cfg.commits_path else None,
        include_graph_cards=cfg.chunking.include_graph_cards,
        include_constant_cards=cfg.chunking.include_constant_cards,
    )
    embedder = create_embedder(
        cfg.embedder.type, dim=cfg.embedder.dim,
        model_name=_resolve_model_name(cfg.embedder.model_name, root),
    )
    vectors = embedder.embed([c.text for c in chunks])

    store = FaissVectorStore(dim=embedder.dim)
    store.add(vectors, chunks)
    store.save(root / cfg.index_dir)

    by_kind: dict[str, int] = {}
    for c in chunks:
        by_kind[c.kind] = by_kind.get(c.kind, 0) + 1
    return {"n_chunks": len(chunks), "by_kind": by_kind, "index_dir": str(root / cfg.index_dir)}


def _create_backend(cfg: ExperimentConfig, embedder: Embedder, project_root: Path) -> RetrievalBackend:
    """按配置实例化检索后端。新后端(如 RepoMind)在这里注册。
    rerank 是正交开关:任何后端都可以再包一层 RerankingBackend(装饰器模式)。"""
    if cfg.backend.type == "local_rag":
        store = FaissVectorStore.load(project_root / cfg.index_dir)
        backend: RetrievalBackend = LocalRagBackend(embedder, store)
    elif cfg.backend.type == "hybrid":
        store = FaissVectorStore.load(project_root / cfg.index_dir)
        backend = HybridBackend(
            embedder, store,
            vector_weight=cfg.backend.vector_weight,
            bm25_weight=cfg.backend.bm25_weight,
        )
    elif cfg.backend.type == "none":
        backend = NoRetrievalBackend()  # 纯 LLM 无 RAG 对照
    elif cfg.backend.type == "repomind":
        backend = RepoMindBackend()  # 占位:调用时会抛 NotImplementedError 并给出指引
    else:
        raise ValueError(f"未知 backend 类型: {cfg.backend.type}")
    if cfg.backend.rerank:
        backend = RerankingBackend(
            backend, candidates=cfg.backend.rerank_candidates,
            scorer=cfg.backend.rerank_scorer, embedder=embedder,
            cross_encoder_path=_resolve_model_name(cfg.backend.rerank_model, project_root),
        )
    # M11:融合检索按 kind 分槽(包在 rerank 之外)。任一槽位 >=0 即启用。
    if cfg.backend.fusion_dep >= 0 or cfg.backend.fusion_sim >= 0:
        backend = FusionBackend(
            backend,
            n_dep=max(0, cfg.backend.fusion_dep),
            n_sim=max(0, cfg.backend.fusion_sim),
        )
    return backend


class RagPipeline:
    """在线问答管道。构造时加载索引,之后 answer 可被反复调用(评测就是循环调它)。"""

    def __init__(self, cfg: ExperimentConfig, project_root: str | Path = "."):
        root = Path(project_root)
        self.cfg = cfg
        # 注意:查询用的 embedder 必须和建索引时**完全一致**,
        # 否则向量空间对不上,检索结果是噪声。两边都从同一份配置创建来保证这点。
        self.embedder = create_embedder(
            cfg.embedder.type, dim=cfg.embedder.dim,
            model_name=_resolve_model_name(cfg.embedder.model_name, root),
        )
        self.backend = _create_backend(cfg, self.embedder, root)
        self.llm: LLM = create_llm(
            cfg.llm.type, max_lines=cfg.llm.max_lines,
            model=cfg.llm.model, base_url=cfg.llm.base_url, temperature=cfg.llm.temperature,
        )
        self.prompt_cfg = PromptConfig.from_yaml(root / cfg.prompt_file)

    def answer(self, question: str) -> PipelineResult:
        retrieved = self.backend.retrieve(question, top_k=self.cfg.backend.top_k)
        prompt = build_prompt(question, retrieved, self.prompt_cfg)
        answer = self.llm.generate(prompt)
        return PipelineResult(question=question, answer=answer, retrieved=retrieved, prompt=prompt)
