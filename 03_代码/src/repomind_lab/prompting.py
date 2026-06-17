"""Prompt 组装 —— PE(Prompt Engineering)实验台的核心。

把 prompt 的三个可调旋钮做成**配置项**(而不是写死在代码里):
  1. system   — 系统提示词:给模型设定角色和回答规范
  2. few_shot — 少样本示例:给几个"问题→理想回答"的例子,教模型输出格式
  3. cot      — 思维链开关:要求模型先一步步分析再给结论

这样"换一种问法"= 换一个 YAML 文件,跑同一套评测就能并排对比效果,
不需要改任何代码 —— 这就是"PE 实验台"的含义。

prompt 的整体结构(标记行如 [代码片段 N] 是协议的一部分,
ExtractiveMockLLM 靠这些标记解析出上下文,改动时要同步改 llm.py):

    {system}
    {few_shot 示例们}
    请根据以下检索到的代码仓库片段回答问题。
    [代码片段 1] 来源: payment/gateway.py (第 1-40 行)
    ...片段内容...
    [问题] ...
    {cot 指令}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .types import RetrievedChunk

CONTEXT_HEADER = "请根据以下检索到的代码仓库片段回答问题。如果片段中没有答案依据,请明确说\"检索结果中没有找到\",不要编造。"
COT_INSTRUCTION = "请先一步步分析:1) 哪个片段和问题最相关;2) 从中能得到什么信息;最后再给出结论。"


@dataclass
class PromptConfig:
    """一种 prompt 配置 = 一个 PE 实验条件。"""

    name: str = "plain"
    system: str = "你是一个代码仓库助手,根据给出的代码片段准确回答问题。"
    few_shot: list[dict] = field(default_factory=list)  # [{question, answer}, ...]
    cot: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PromptConfig":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", Path(path).stem),
            system=data.get("system", cls.system),
            few_shot=data.get("few_shot", []),
            cot=bool(data.get("cot", False)),
        )


def format_context(retrieved: list[RetrievedChunk]) -> str:
    """把检索结果格式化成带来源标注的片段列表。

    标注来源(文件 + 行号)有两个目的:
    1. 让模型能回答"在哪个文件"类问题 —— 答案就在标注里
    2. 真实场景下让用户能核查答案出处(可解释性)
    """
    parts = []
    for i, rc in enumerate(retrieved, start=1):
        c = rc.chunk
        if c.kind == "commit":
            header = f"[代码片段 {i}] 来源: 提交历史 {c.source}"
        else:
            header = f"[代码片段 {i}] 来源: {c.source} (第 {c.start_line}-{c.end_line} 行)"
        parts.append(f"{header}\n{c.text}")
    return "\n\n".join(parts)


def build_prompt(question: str, retrieved: list[RetrievedChunk], cfg: PromptConfig) -> str:
    """按配置组装最终 prompt。各段顺序:system -> few-shot -> 上下文 -> 问题 -> CoT。"""
    sections = [cfg.system]

    if cfg.few_shot:
        examples = []
        for ex in cfg.few_shot:
            examples.append(f"[示例问题] {ex['question']}\n[示例回答] {ex['answer']}")
        sections.append("以下是回答的参考范例:\n" + "\n\n".join(examples))

    # 纯 LLM 对照(无 RAG)时 retrieved 为空:不挂"请根据以下片段"的脚手架,
    # 直接问,公平地考模型自身的参数化知识(M3-B E18)。
    if retrieved:
        sections.append(CONTEXT_HEADER)
        sections.append(format_context(retrieved))
    sections.append(f"[问题] {question}")

    if cfg.cot:
        sections.append(COT_INSTRUCTION)

    return "\n\n".join(sections)
