# BONUS_FINDINGS.md — 四个超额项归档(M68-71,非考题要求)

> **定位**:以下四项**不是官方五道考题要求**,是补考收口后用余力做的 C 类超额探索。
> 各项标【实验 + 结论 + 边界 + 超额标注】,均**判分无关、可独立复现**(`03_代码/scripts/verify_bonus.py`,无 GPU/无模型)。
> **红线一致**:判分无关为主、0 self-judge、全样本、诚实负向/边界、不灌水成"新发现"、不与主线混淆。
> 主索引 `INDEX.md`、考题对照 `EXAM_COVERAGE_MATRIX.md` §六 均列出本文。

---

## §1 超额一(M68):rerank 掩盖 embedding 选型——交叉编码器把"语言选错"的代价兜回

**实验**:同一检索任务,三种 embedding(zh 中文 bge=选错 / MiniLM 中性 / en 英文=正确)× rerank(off/on),量 Recall@5 与 MRR。脚本 `pe31_embed_impact.py`/`pe32`,结果 `05_评测结果/pe32_rerank_masking.json`。

| embedding | R@5 off | R@5 on | MRR off | MRR on |
|---|---|---|---|---|
| zh(选错) | 0.321 | 0.929 | 0.256 | 0.874 |
| MiniLM(中性) | 0.804 | 0.982 | 0.640 | 0.926 |
| en(正确) | 0.929 | 0.982 | 0.817 | 0.923 |

**结论**:无 rerank 时 en−zh 的 MRR 差距 **0.561**;加 rerank 后差距塌到 **0.049**——**rerank 把"embedding 选错语言"的代价压缩 ~11.3×**。选错语言的 embedding 被交叉编码器重排兜回。这解释了为何项目早期用错 embedding 主线分数仍稳(全栈有 rerank 兜底)。

**边界(诚实)**:rerank 只**重排**召回池、**不新增召回**;候选池里必须先有答案才救得回,**池外漏的 rerank 救不回**。所以"embedding 选型不重要"只在"有强 rerank 且答案已在池内"成立,不能推广成"embedding 随便选"。

---

## §2 超额二(M69):源头预防(System Prompt) > 末端纠正(后处理 filter)

**实验**:2×2——System 反幻觉约束(on/off)× 后处理 filter,固定上下文只变 System Prompt。幻觉 = 预测的 `.py` 文件不在提供的上下文里(编造)。脚本 `pe33_build_sysabl.py`/`pe36_sysabl_analysis.py`,结果 `05_评测结果/scores_sysabl.json`。

| 条件 | 未接地(编造)预测数 | 预测总数 | 幻觉率 | dep-recall |
|---|---|---|---|---|
| System-OFF | 267 | 314 | 0.850 | 0.655 |
| System-ON | 91 | 142 | 0.641 | 0.611 |

**结论**:System Prompt 在**源头**把未接地文件名预测从 **267→91(减 66%)**,仅付 0.04 dep-recall 代价;**后处理 filter 只能事后剔除,但 System-ON 预防后已所剩无几,filter 无可纠正(M64 实测 Δ=0)**。→ 工程原则:**同类错误(编造文件名),源头 System Prompt 预防 > 末端 filter 纠正**,更彻底、代价更小。

**边界(诚实)**:① 绝对幻觉率受"路径形 vs 模块形"文本匹配噪声影响,**相对减少 ~66% 才是稳健信号**(已标);② filter 与 System Prompt 都只对付"编造上下文没有的文件名",**对 over-inclusion(列了上下文有但不相关的项=precision)两者都不直接管**,那需相关性过滤(另一类后处理)。

---

## §3 超额三(M70):det-recall vs LLM-judge 系统对照——双向分歧、互补,非谁取代谁

**实验**:同一批 werkzeug 答案,judge-independent 的 det-recall(keyword_all 结构召回)对照各报告记录的 LLM-judge 分。脚本 `pe35_det_vs_judge.py`,数据 `05_评测结果/answers_werkzeug_*` + `04_数据/testcases_werkzeug.jsonl`。

| 配置 | det-recall(结构召回) | LLM-judge(综合质量) | judge−det |
|---|---|---|---|
| baseline | 0.160 | 0.19 | +0.030 |
| full RAG | 0.747 | 0.94 | **+0.193** |
| PE all | 0.854 | 0.79 | **−0.064** |
| PE cot | 0.859 | 0.80 | **−0.059** |

**结论(焊死)**:**两指标测不同东西,且双向分歧**——简洁但不全的答案 judge>det(裁判给部分分);完整但啰嗦的 CoT/PE det>judge(裁判罚 det 看不见的风格/格式)。**det-recall** = 结构召回(客观无裁判偏差但窄),**LLM-judge** = 综合质量(全面但主观+宽松~0.2+偏好+对完整性不敏感)。**互补,绝非"我的指标才对"**。这正向佐证项目"承重结论用 judge-independent 为主指标"的合理性——不是 judge 错,是承重结论不该压在有偏差的主观裁判上。

**边界(诚实)**:det 盲区=结构全但推理错的答案 det 仍高;judge 盲区=不全但流畅给部分分、完整性增益被低估、裁判个体偏好。两者都有盲点,需并用。

---

## §4 超额四(M71):长上下文位置效应 = recency 非经典 LITM,跨模型 + 任务依赖性边界

**实验**:权威卡片放进 ~44k 上下文的 5 个位置(0/25/50/75/100%)+ 跨两模型,量 dep-recall。脚本 `pe34_build_poslong.py`/`pe37_poslong_analysis.py`,结果 `05_评测结果/scores_poslong_{coder,qwen}.json`。

| 模型 | pos0 | pos25 | pos50 | pos75 | pos100 | recency(末−开) |
|---|---|---|---|---|---|---|
| Coder-14B | 0.702 | 0.736 | 0.727 | 0.800 | 0.982 | **+0.280** |
| Qwen-14B | 0.900 | 0.915 | 0.910 | 0.899 | 0.955 | +0.055 |

**结论**:**方向 = recency(末尾最好),跨两模型一致;非经典 lost-in-the-middle**(中间 pos50 不是最差,开头 pos0 才最差)。**幅度模型依赖**:Coder-14B 强位置敏感(+0.28),Qwen-14B 近位置鲁棒(+0.06,长上下文处理强、各位置都 ~0.90-0.96)。深化 M66 长上下文诊断。

**边界(诚实,不过度推广)**:本任务是"找**一条权威依赖信息**"(单点检索)非"综合多处"——recency 可能是该单点检索任务的特性,**不普适到所有长上下文场景**(综合类任务可能呈 U 形 LITM)。这是诊断深化,**非普适规律**。

---

## 复现

```
python 03_代码/scripts/verify_bonus.py
```
无 GPU、无模型,从交付内 `05_评测结果/` 的结果 json + `04_数据/` 的 gold 判分无关重算上述全部数字(M68 的 11.3×、M69 的 267→91、M70 的 det 表、M71 的位置曲线)。各超额对应的原始脚本(`pe31-pe37`/`task3_*`/`pe33-pe37`)在 `03_代码/scripts/`。
