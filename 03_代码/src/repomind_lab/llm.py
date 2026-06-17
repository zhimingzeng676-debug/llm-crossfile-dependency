"""LLM 接口 + 本地 Mock 实现。

当前环境没有可用的大模型 API,但整条链路和评测框架不能等 ——
所以 LLM 也抽象成接口,先用一个"抽取式 Mock"顶上:

ExtractiveMockLLM 的"回答"方式:
  1. 从 prompt 里解析出 [代码片段 N] 上下文和 [问题](依赖 prompting.py 的标记协议)
  2. 把问题分词,逐行给上下文里的每一行打"词重合度"分
  3. 挑得分最高的几行 + 它们的来源标注,拼成回答

它显然不是真的语言模型,但有一个对今晚至关重要的性质:
**它的回答质量完全取决于检索质量** —— 检索对了,相关行就在上下文里,
关键词判定就能通过;检索错了,怎么抽都抽不出正确答案。
因此评测分数 = 检索效果的真实信号,消融实验(切块策略、top-k)的对比是有意义的,
而不是在随机数上自欺欺人。

局限(诚实地写在这里):
- 它不会推理、不会综合多个片段,所以"为什么"类问题的分数会系统性偏低;
- CoT / few-shot 等 PE 配置对它几乎无效(它不读指令)——
  PE 实验台的基础设施今晚建好,**真实的 PE 对比要等接入真 LLM**(见 NEXT_STEPS)。
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .embedding import tokenize


class LLM(ABC):
    """大模型接口:prompt 进,文本回答出。"""

    @abstractmethod
    def generate(self, prompt: str) -> str: ...

    @property
    def name(self) -> str:
        return type(self).__name__


# 与 prompting.py 的标记协议对应(改这边要同步改那边)
_SNIPPET_RE = re.compile(r"^\[代码片段 \d+\] 来源: (.+)$")
_QUESTION_RE = re.compile(r"^\[问题\] (.+)$")

# "意图启发式"用到的模式(见 ExtractiveMockLLM docstring)
_CALL_INTENT_RE = re.compile(r"调用|call", re.IGNORECASE)
_WHO_WHEN_RE = re.compile(r"谁|什么时候|何时|哪天|作者|when|who", re.IGNORECASE)
_CALL_NAME_RE = re.compile(r"([A-Za-z_]\w*)\s*\(")
_DEF_RE = re.compile(r"^\s*def\s+(\w+)")
# 形如 xxx( 但并非函数调用的常见词(语法关键字等)
_NOT_CALLS = {"if", "elif", "for", "while", "def", "return", "with", "assert", "not", "and", "or", "in", "lambda", "class"}


class ExtractiveMockLLM(LLM):
    """抽取式 Mock(原理见模块 docstring)。max_lines 控制回答里最多引用几行。

    除了基础的"词重合度选行",还有两条意图启发式(模拟真 LLM 的基本理解能力,
    初版没有它们时,实测"谁改的"答不出作者、"调用了谁"答不出被调函数):
    1. 问题含"调用/call"时,改走"调用提取"模式:挑出与问题最相关的片段,
       用正则提取其中所有 `名字(` 形式的调用,直接列出被调函数名。
       (逐行打分对这类问题天然失效:调用语句和问题几乎没有词面重合);
    2. 提交历史片段只要有任何一行相关,就整段引用(commit 块只有 3 行,作者/日期
       和 message 是一体的,拆开引用会丢掉"谁、什么时候"这一半信息);
    3. 注释行命中问题时,把分数的 0.8 倍传递给它下面那行代码(注释描述的是
       下一行,答案数值往往在代码行里而代码行和中文问题零词面重合);
    4. 问题含"谁/什么时候"时,相关 commit 块的首行(提交 hash 作者: X 日期: Y)
       强力加分 —— 该行是这类问题的直接答案,但与问题永远零词面重合,
       只靠启发式 2 的 +0.6 仍会被有词面重合的代码行挤出答案(HI-03 实测);
    5. 空关系行("它调用的仓库内函数: (无)"这类)重打折 —— 它们信息量为零,
       却因为中文 2-gram 的巧合("调用的"切出"用的"恰与问题重合)得分虚高,
       会把真正含答案的行挤出名额(best_stack 下 CC-03 实测归零)。
    """

    def __init__(self, max_lines: int = 6):
        self.max_lines = max_lines

    def generate(self, prompt: str) -> str:
        # --- 1. 解析 prompt:还原出 (来源, 内容行们) 列表和问题 ---
        snippets: list[tuple[str, list[str]]] = []  # (来源标注, 行列表)
        question = ""
        current_lines: list[str] | None = None
        for line in prompt.splitlines():
            m = _SNIPPET_RE.match(line)
            if m:
                current_lines = []
                snippets.append((m.group(1), current_lines))
                continue
            m = _QUESTION_RE.match(line)
            if m:
                question = m.group(1)
                current_lines = None  # 问题之后的内容(如 CoT 指令)不算上下文
                continue
            if current_lines is not None:
                current_lines.append(line)

        if not question or not snippets:
            return "(MockLLM)prompt 里没有解析到问题或上下文,无法回答。"

        q_tokens = set(tokenize(question))

        # --- 启发式 1:"调用"类问题走调用提取模式 ---
        if _CALL_INTENT_RE.search(question):
            extracted = self._extract_calls(q_tokens, snippets)
            if extracted is not None:
                return extracted

        # --- 2. 给每一行打分:词重合度 + 来源加成 ---
        who_when = bool(_WHO_WHEN_RE.search(question))
        scored: list[tuple[float, str, str]] = []  # (得分, 来源, 行文本)
        seen_lines: set[tuple[str, str]] = set()   # 去重(overlap 切块会产生重复行)
        for source, lines in snippets:
            src_bonus = len(q_tokens & set(tokenize(source))) * 0.5  # 来源路径本身也算证据
            is_commit = source.startswith("提交历史")
            overlaps = [len(q_tokens & set(tokenize(line))) for line in lines]
            snippet_relevant = any(o > 0 for o in overlaps) or src_bonus > 0
            # 启发式 3:注释描述的是它下面的代码 —— 注释行命中时把分数部分传给下一行。
            # (实测案例:"# 单笔超过该金额视为大额" 匹配了问题,而真正含答案数值的
            #  LARGE_AMOUNT_THRESHOLD = 500_000 在它下一行,词面重合为零会落选)
            passed = [0.0] * len(lines)
            for i in range(len(lines) - 1):
                if lines[i].strip().startswith("#") and overlaps[i] > 0:
                    passed[i + 1] += overlaps[i] * 0.8
            for i, (line, overlap) in enumerate(zip(lines, overlaps)):
                if not line.strip():
                    continue
                score = overlap + passed[i] + src_bonus
                # 启发式 2:相关的 commit 块整段引用(作者/日期行单独看重合度是 0)
                if is_commit and snippet_relevant:
                    score += 0.6
                    # 启发式 4:"谁/什么时候"问题里,作者/日期行就是直接答案
                    if who_when and line.startswith("提交 "):
                        score += 2.0
                # 启发式 5:空关系行(信息量为零)重打折
                if line.rstrip().endswith("(无)") or "没有仓库内" in line:
                    score *= 0.2
                key = (source, line.strip())
                if score > 0 and key not in seen_lines:
                    seen_lines.add(key)
                    scored.append((score, source, line.strip()))

        if not scored:
            return "(MockLLM)检索结果中没有找到与问题相关的内容。"


        # --- 3. 取最高分的行拼成回答;来源去重保序,放在开头 ---
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[: self.max_lines]
        sources: list[str] = []
        for _, src, _ in top:
            if src not in sources:
                sources.append(src)
        body = "\n".join(f"  {line}" for _, _, line in top)
        return f"根据检索到的代码,相关内容位于 {';'.join(sources)}:\n{body}"

    def _extract_calls(self, q_tokens: set[str], snippets: list[tuple[str, list[str]]]) -> str | None:
        """调用提取模式:在与问题最相关的片段里,正则找出所有函数调用名。

        返回 None 表示"没有足够相关的片段",让调用方退回普通逐行抽取模式。
        """
        # 选最相关片段:行重合度总和 + 来源加成。全为 0 则放弃。
        def relevance(snippet: tuple[str, list[str]]) -> float:
            source, lines = snippet
            src_bonus = len(q_tokens & set(tokenize(source)))
            return sum(len(q_tokens & set(tokenize(line))) for line in lines) + src_bonus

        best = max(snippets, key=relevance)
        if relevance(best) <= 0:
            return None
        source, lines = best

        # 片段里定义的函数名不算"被调用方"(def 行也会匹配 名字( 模式)
        defined = {m.group(1) for line in lines for m in [_DEF_RE.match(line)] if m}
        calls: list[str] = []
        for line in lines:
            if _DEF_RE.match(line):
                continue
            for m in _CALL_NAME_RE.finditer(line):
                name = m.group(1)
                if name not in _NOT_CALLS and name not in defined and name not in calls:
                    calls.append(name)
        if not calls:
            return None
        return (
            f"根据检索到的代码({source}),其中发起的函数/构造调用有: "
            f"{', '.join(calls)}。"
        )


class ApiLLM(LLM):
    """真实大模型客户端(第二阶段兑现,"填 key 即用")。

    走 OpenAI 兼容的 chat completions 协议 —— 混元、DeepSeek、通义、OpenAI
    等主流服务都支持这个格式,所以一个实现通吃。用标准库 urllib 而不装
    openai SDK:我们只需要一个端点,没必要为它引入一整套依赖(及其网络下载风险)。

    启用步骤(评测框架零改动):
      1. 设置环境变量:  $env:LLM_API_KEY = "sk-..."
      2. 实验配置里:
           llm:
             type: api
             model: hunyuan-turbo            # 或 deepseek-chat 等
             base_url: https://api.hunyuan.cloud.tencent.com/v1
      3. 正常跑 run_eval / run_ablation。此时 PE 实验(plain vs cot vs few-shot)
         才真正生效 —— MockLLM 不读指令,真模型读。

    设计说明:prompting.py 组装的完整 prompt(含 system/few-shot/上下文)作为
    单条 user 消息发送。更标准的做法是把 system 拆成独立 message,
    留作接入后的小优化(不影响对比实验的公平性,所有配置同样处理)。
    """

    def __init__(self, model: str = "", api_key: str = "", base_url: str = "",
                 temperature: float = 0.0, timeout: int = 60):
        import os

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.temperature = temperature  # 评测要可复现,默认 0(最确定性的采样)
        self.timeout = timeout
        if not self.model or not self.base_url:
            raise ValueError(
                "llm.type: api 需要在配置里给出 model 和 base_url(OpenAI 兼容端点),"
                "例如 base_url: https://api.hunyuan.cloud.tencent.com/v1"
            )
        if not self.api_key:
            raise ValueError("未找到 API key:请设置环境变量 LLM_API_KEY(或在配置里写 api_key)")

    def generate(self, prompt: str) -> str:
        import json
        import time
        import urllib.error
        import urllib.request

        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        # 批量评测要扛住隧道/服务的偶发抖动:重试 4 次,指数退避。
        last_err = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
                detail = ""
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        detail = e.read().decode("utf-8", "replace")[:300]
                    except Exception:
                        pass
                if attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"ApiLLM 调用失败(已重试 {attempt + 1} 次):{e} {detail}") from last_err


def create_llm(type_: str = "mock", **kwargs) -> LLM:
    """工厂函数:配置字符串 -> LLM 实例。"""
    if type_ == "mock":
        return ExtractiveMockLLM(max_lines=kwargs.get("max_lines", 6))
    if type_ == "api":
        return ApiLLM(
            model=kwargs.get("model", ""),
            base_url=kwargs.get("base_url", ""),
            api_key=kwargs.get("api_key", ""),
            temperature=kwargs.get("temperature", 0.0),
        )
    raise ValueError(f"未知 llm 类型: {type_}(可选 mock / api)")
