"""实验配置:一个 YAML 文件 = 一组完整的实验条件。

为什么配置驱动:消融实验的本质是"只改一个变量,其他全部不动"。
把所有可变量(切块策略、embedding、top-k、prompt 风格……)收进一个配置文件,
对比实验就变成"复制 baseline.yaml,改一行,跑 run_ablation" ——
不改代码、不会改漏、配置文件本身就是实验记录。

用 pydantic 定义结构的好处:字段名拼错、类型不对会在**加载时**报清晰的错,
而不是跑了半天评测后在某个深处炸掉。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class ChunkingConfig(BaseModel):
    strategy: str = "fixed"        # fixed / function
    chunk_lines: int = 40          # 仅 fixed 策略使用
    overlap: int = 10              # 仅 fixed 策略使用
    include_graph_cards: bool = False  # 是否把调用图文本化成卡片一并索引(救反向查询)
    include_constant_cards: bool = False  # 是否把模块级常量做成卡片(救常量盲区,E12)

    @model_validator(mode="after")
    def check_overlap(self):
        if self.strategy == "fixed" and not (0 <= self.overlap < self.chunk_lines):
            raise ValueError("overlap 必须满足 0 <= overlap < chunk_lines")
        return self


class EmbedderConfig(BaseModel):
    # pydantic 默认保护 model_ 前缀的字段名,这里明确放行(model_name 是业界惯用名)
    model_config = {"protected_namespaces": ()}

    type: str = "hashing"          # hashing / sentence_transformer
    dim: int = 512                 # 仅 hashing 使用
    # 仅 sentence_transformer 使用:HF 模型 ID 或本地目录(相对项目根,pipeline 会解析)
    model_name: str = "models/bge-small-zh-v1.5"


class BackendConfig(BaseModel):
    type: str = "local_rag"        # local_rag / hybrid / repomind(占位)
    top_k: int = 3
    # 仅 hybrid 使用:两路召回的 RRF 权重
    vector_weight: float = 1.0
    bm25_weight: float = 1.0
    # 任意后端可叠加的重排序开关:先召回 rerank_candidates 个再精排截断 top_k
    rerank: bool = False
    rerank_candidates: int = 10
    rerank_scorer: str = "lexical"  # lexical(E5)/ embedder(E9)/ cross_encoder(E11)
    rerank_model: str = "models/bge-reranker-base"  # 仅 cross_encoder 用,目录相对项目根
    # M11 融合检索:把检索结果按 kind 分配槽位 —— 依赖图卡片(graph) vs 相似代码(function/code)。
    # 任一 >=0 即启用 FusionBackend(包在 rerank 之外);-1 表示不启用(用普通 top_k)。
    fusion_dep: int = -1           # 依赖卡片槽位数(纯依赖 = 满额 dep,sim=0)
    fusion_sim: int = -1           # 相似代码槽位数(纯相似度 = 满额 sim,dep=0)


class LLMConfig(BaseModel):
    type: str = "mock"             # mock / api(已实现,填 key 即用,见 llm.ApiLLM)
    max_lines: int = 6             # 仅 mock 使用
    # 仅 api 使用(api_key 建议走环境变量 LLM_API_KEY,不要写进配置文件提交)
    model: str = ""
    base_url: str = ""
    temperature: float = 0.0


class ExperimentConfig(BaseModel):
    """一次实验的全部条件。name 会出现在结果文件名和对比报告里。"""

    name: str
    repo_root: str = "mock_repo"
    commits_path: str | None = "data/mock_commits.jsonl"  # None 表示不索引提交历史
    index_dir: str = ""            # 留空则自动用 indexes/<name>/
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedder: EmbedderConfig = Field(default_factory=EmbedderConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    prompt_file: str = "configs/prompts/plain.yaml"

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        cfg = cls(**data)
        if not cfg.index_dir:
            cfg.index_dir = f"indexes/{cfg.name}"
        return cfg
