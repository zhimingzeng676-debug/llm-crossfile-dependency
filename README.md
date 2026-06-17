# 基于微调 / PE / RAG 的代码分析领域效果优化 —— LLM 跨文件依赖理解

> 腾讯 mini 项目(方向:跨文件依赖分析,中难度)。本仓库是完整交付:报告 + 代码 + 数据 + 评测结果 + 无 GPU 可复现包。

## 一句话结论
**提升 LLM 跨文件依赖能力的有效路径 = 把确定性算好的结构事实(RAG 依赖卡片)喂进上下文,而非改造模型本身**;PE / 微调在这类任务上回报边际——因为依赖是**可精确计算的结构事实**,让模型去读/猜/学着逼近,都赢不过直接算出来再喂给它。中难度考题五大块(瓶颈诊断 / PE / RAG / 微调 / 消融)全覆盖,逐条对照见下。

> ⚠ **编号说明**:本项目实验以**里程碑(milestone)编号 `M1…M76` 迭代,代表 prompt 驱动的迭代里程碑、非自然天数**——请勿按字面理解为开发天数。
> ⚠ **口径说明**:所有"真值"为**静态解析器(ast/tree-sitter/gcc/javalang)或 git co-change 派生**,非开发者主观真实依赖;严谨地说本项目证明"让模型高保真复现可计算的依赖结构",而非"解决了依赖理解"。

## 考题逐条对照(评审入口)
**→ `01_报告/EXAM_COVERAGE_MATRIX.md`**:五大块逐子项 → 对应交付文件 + 状态,无空格。
其它入口:`01_报告/INSIGHT.md`(核心见解)、`01_报告/VALUE_FOR_REPOMIND.md`(甲方决策语言)、`01_报告/EVALUATION_REPORT.md`(量化评测/消融)。

## 目录结构
```
01_报告/                 报告与方法论(诊断/PE方案/评测/消融/诚实修正链/文献定位…)
02_模型微调权重/          adapter 配置 + 权重说明(权重本体超100MB未提交,见 WEIGHTS_NOTE.md)
03_代码/                 src/repomind_lab(RAG pipeline) + scripts(实验/复现脚本)
04_数据/                 测试用例(gold)、微调/检索训练数据、跨语言用例
05_评测结果/             各配置答案 + 分数 json(含跨模型/超参扫描/embedding 复现结果)
06_开发者真值发现/        co-change 开发者真值发现 + 无 GPU 一键复现 verify_finding.py + md5
```
> 注:考题答卷 / 学习笔记 / 简历等**个人材料不在本公开仓库**(单独随提交渠道提供);本仓库为可公开的代码与方法论交付。

## 如何复现(无 GPU,克隆即可跑)
环境:Python 3.10。两条主复现链**不需要 GPU、不需要模型**,纯字符串/统计判分无关复算:

```bash
# 1) 开发者真值发现(co-change 负杠杆机理、补盲传递函数等)
cd 06_开发者真值发现 && python verify_finding.py
#   预期:打印 mechanism(McNemar p≈0.94 机械挤占)、transfer recall≈0.16+0.82*cov 等,结尾 [verify_finding] done.

# 2) 四个超额项(rerank掩盖11.3× / 预防>纠正 267→91 / det-vs-judge / 位置效应recency)
python 03_代码/scripts/verify_bonus.py        # 从仓库根运行
#   预期:打印 4 段结果(11.4x、sys_off 267→sys_on 91、full RAG det 0.747、Coder pos recency +0.280),结尾 done.
```

**其它脚本**(`03_代码/scripts/` 下 `pe*`/`xmodel*`/`ft_sweep`/`verify_embed_indep` 及 `remote/`)**需要 GPU 推理服务 / 外部模型 / 第三方源码**,用于实验透明性、非克隆即跑;依赖与环境变量在各脚本头部注明(如 `verify_embed_indep.py` 需 `WERKZEUG_SRC` + 联网拉 embedding 模型)。

## 权重
QLoRA adapter 权重(~263MB)超 GitHub 100MB 限制**未提交**,见 `02_模型微调权重/WEIGHTS_NOTE.md`(含复现训练命令);完整规格见 `01_报告/MODEL_CARD.md`。


## 检索冒烟测试(过程护栏)
```bash
python tests/smoke_retrieval.py   # 退出码非0=有退化
```
几条十行级断言,**第一天就能拦住 embedding 选错语言 / 检索退化 / 卡片生成为空** 这类沉默退化:卡片生成非空、检索返回格式正确、**英文 embedding 在英文代码语料上不弱于中文 embedding**(需 sentence-transformers + bge 模型,无则自动 SKIP)。
> 诚实定位:**此护栏是事后补充的教训**——本项目的「embedding 选错语言」bug 跑了约两个月才偶然发现、当时缺这种烟雾报警器;补上它是把「会救火」补成「会装报警器」,如实记录、不掩饰。

## 诚实性
本项目核心结论以 **LLM-judge-independent(parser-anchored)指标为主**、0 self-judge、配对统计、去同源循环;含 15+ 次有据自我修正(`01_报告/HONEST_TRAJECTORY.md`)与修复状态(`FIX_STATUS.md`)。主线 RAG 主导 / PE·微调边际经**跨 3 模型 2 家族双口径**验证(`CROSS_MODEL_GENERALIZATION.md`),并与 2025 顶会实证一致(`PE_SOLUTION.md` §八;相关工作 / 文献定位见 `RELATED_WORK.md`)。
