"""判定器:把"这个答案对不对"变成 0~1 的分数。

为什么用规则判定而不是人工看:评测要跑几十条用例 × 多个配置,
人工看不可持续,也不可复现。规则判定(关键词/正则)虽然粗糙,
但**确定、便宜、可复现**,适合做消融对比的主指标。
(更高级的"LLM 当裁判"打分法放在 NEXT_STEPS —— 需要真模型。)

三种判定类型:
- keyword_all:答案须包含全部关键词,得分 = 命中数/总数(给部分分,
  比如调用链问题列出 3 个被调函数中的 2 个,得 0.67 而不是 0 ——
  部分分让配置间的差异更平滑、更可比)
- keyword_any:命中任意一个即满分(同一个事实有多种说法时用,
  比如"30 天"和"REFUND_WINDOW_DAYS"都算答对)
- regex:正则匹配,处理更复杂的模式

判定一律忽略大小写(代码标识符的大小写在自然语言回答里不稳定)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .testcase import JudgeSpec


@dataclass
class JudgeResult:
    score: float          # 0.0 ~ 1.0
    detail: str           # 人类可读的判定依据(报告里展示,方便复查误判)


def judge_answer(answer: str, spec: JudgeSpec) -> JudgeResult:
    """按 spec 判定 answer,返回分数与依据。"""
    text = answer.lower()

    if spec.type == "keyword_all":
        hits = [kw for kw in spec.keywords if kw.lower() in text]
        misses = [kw for kw in spec.keywords if kw.lower() not in text]
        score = len(hits) / len(spec.keywords) if spec.keywords else 0.0
        return JudgeResult(score, f"命中 {hits},缺失 {misses}")

    if spec.type == "keyword_any":
        hits = [kw for kw in spec.keywords if kw.lower() in text]
        return JudgeResult(1.0 if hits else 0.0, f"命中 {hits}" if hits else f"全部未命中 {spec.keywords}")

    if spec.type == "all_groups":
        # 每组 = 同一事实的若干种说法(任中一个);组间 = 不同事实(全都要)。
        # 得分 = 通过的组数 / 总组数(与 keyword_all 一样给部分分)。
        passed, failed = [], []
        for group in spec.groups:
            hits = [kw for kw in group if kw.lower() in text]
            (passed if hits else failed).append(f"{group}->{hits or '未中'}")
        score = len(passed) / len(spec.groups) if spec.groups else 0.0
        return JudgeResult(score, f"通过组 {passed},未过组 {failed}")

    if spec.type == "regex":
        m = re.search(spec.pattern, answer, re.IGNORECASE)
        return JudgeResult(1.0 if m else 0.0, f"正则 {spec.pattern!r} " + ("匹配" if m else "未匹配"))

    raise ValueError(f"未知判定类型: {spec.type}")


def judge_retrieval(retrieved_sources: list[str], expected_sources: list[str]) -> JudgeResult:
    """检索命中判定:任一预期来源出现在检索结果里即命中(召回视角)。

    用前缀匹配:expected 写 "payment/fees.py" 能匹配块 "payment/fees.py#L1-24",
    写 "commit:M92b4e7" 能匹配该 commit 块。
    没写 expected_sources 的用例返回 -1 表示"不适用",聚合时跳过。
    """
    if not expected_sources:
        return JudgeResult(-1.0, "该用例未标注预期来源,不计检索分")
    for exp in expected_sources:
        for src in retrieved_sources:
            if src.startswith(exp):
                return JudgeResult(1.0, f"检索命中 {exp}")
    return JudgeResult(0.0, f"预期 {expected_sources},实际 {retrieved_sources}")


def _is_relevant(src: str, expected_sources: list[str]) -> bool:
    """一个检索来源是否命中任一预期来源(前缀匹配,与 judge_retrieval 同口径)。"""
    return any(src.startswith(exp) for exp in expected_sources)


def retrieval_metrics(retrieved_sources: list[str], expected_sources: list[str]) -> dict:
    """标准 IR 检索指标(考核 RAG 评分项要求 Recall@K / MRR)。

    输入 retrieved_sources 已按相关度降序(检索返回顺序)。定义:
    - recall@k:预期来源里被检回的**占比** = |命中的预期来源| / |全部预期来源|。
      对多答案用例(如"哪些文件依赖 X",X 可能被多文件依赖)能衡量覆盖度,
      不像 0/1 的 hit 只看"沾边没有"。
    - MRR(Mean Reciprocal Rank):第一个相关结果的排名倒数 1/rank。
      它惩罚"相关块排在很后面"——正是 rerank 要优化的东西。
    - hit:recall>0 即 1(与旧 retrieval_hit 兼容,聚合时仍可用)。

    没标 expected_sources 的用例三项都返回 None(聚合时跳过)。
    """
    if not expected_sources:
        return {"recall": None, "mrr": None, "hit": None}

    # recall:预期来源里有几个被任一检索块前缀命中
    matched_exp = {exp for exp in expected_sources
                   if any(src.startswith(exp) for src in retrieved_sources)}
    recall = len(matched_exp) / len(expected_sources)

    # MRR:第一个"相关"检索块的排名
    mrr = 0.0
    for rank, src in enumerate(retrieved_sources, start=1):
        if _is_relevant(src, expected_sources):
            mrr = 1.0 / rank
            break

    return {"recall": round(recall, 4), "mrr": round(mrr, 4), "hit": 1.0 if recall > 0 else 0.0}
