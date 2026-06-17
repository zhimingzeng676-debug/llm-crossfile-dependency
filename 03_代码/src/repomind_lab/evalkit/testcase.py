"""测试用例的数据结构。

设计成数据(JSONL 文件)而不是代码,是因为用例会被反复增删、
也可能将来由别人(导师/队友)补充 —— 改数据文件不需要懂这套代码。

每条用例的核心字段(对应任务书要求的 ID/输入/预期输出/判定规则/优先级):
- id           唯一编号,如 CC-01(类别缩写-序号)
- category     方向分类:call_chain / history / cross_file / semantic
               (正好对应课题的四个优化方向,评测报告按它分组出分)
- question     喂给 pipeline 的问题原文
- judge        判定规则(类型 + 参数,见 judges.py)
- expected_sources  预期检索应命中的来源(文件路径前缀或 commit:hash)——
               用来单独计算"检索命中率",把【检索错了】和【检索对了但
               回答没用上】两种失败区分开,这对归因至关重要
- priority     P0(核心能力,必须过)/ P1(重要)/ P2(锦上添花)
- notes        这条用例在考察什么,给读用例的人看
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class JudgeSpec(BaseModel):
    """判定规则:type 决定算法,其余字段是该算法的参数。"""

    type: str  # keyword_all / keyword_any / regex / all_groups
    keywords: list[str] = Field(default_factory=list)
    pattern: str = ""  # 仅 regex 用
    # 仅 all_groups 用:每组内任中一个即该组通过,组间全部要通过(可拿部分分)。
    # 用于"一个事实有多种说法,但多个事实都必须在场"的判定,
    # 例:[["refund.py"], ["30 天", "REFUND_WINDOW_DAYS"]] —— 文件名必须有,
    # 数值用注释说法或常量名说法都算。比裸 "30" 这种会误匹配行号的关键词严谨。
    groups: list[list[str]] = Field(default_factory=list)


class TestCase(BaseModel):
    id: str
    category: str
    question: str
    judge: JudgeSpec
    expected_sources: list[str] = Field(default_factory=list)
    priority: str = "P1"
    difficulty: str = "medium"  # easy / medium / hard(M1-2 新增,难题拉开配置差距)
    notes: str = ""


def load_testcases(path: str | Path) -> list[TestCase]:
    """从 JSONL 加载用例(一行一条;空行和 // 开头的注释行跳过)。"""
    cases: list[TestCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        cases.append(TestCase(**json.loads(line)))
    # ID 必须唯一,重复通常意味着复制粘贴改漏了 —— 尽早报错
    ids = [c.id for c in cases]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ValueError(f"测试用例 ID 重复: {dup}")
    return cases
