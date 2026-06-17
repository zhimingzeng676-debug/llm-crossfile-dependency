# EXAM_COVERAGE_MATRIX.md — 考题验收对照表(M72 归档收口)

> **用途**:对照官方五道考题逐条核对,每条标【对应交付文件 + 状态】,让评委/导师能逐条核对**无空格**。
> **状态口径**:🟢=有完整证据+判分无关复核+边界诚实;本表只标真实达成的 🟢,不虚标。
> **措辞统一(全项目)**:① "数量级"→"主导杠杆/大效应(严打~4-5×、宽松~2×)";② "judge-independent"→"LLM-judge-independent(parser-anchored)";③ 各结论带边界。
> 本表为 M64-71(补考四空格 + 地基核查 + 四超额)收口后的最终覆盖快照。

---

## 一、瓶颈诊断(三大瓶颈,要求:各有【诊断+根因+靶向解+量化】,对称完整)

| 瓶颈 | 诊断 | 根因 | 靶向解 | 量化(判分无关为主) | 交付文件 | 状态 |
|---|---|---|---|---|---|---|
| **① 关联断裂**(跨文件符号失联) | 模型看不到 import/alias/re-export 链,跨文件依赖召回近 0 | 上下文无依赖结构;别名/re-export 链断 | 结构化依赖卡片(import/call/inherit 边)+ alias 链解析 | baseline 0.05→卡片 0.94;符号失联类 0→1.0(别名解析后) | `DIAGNOSIS.md`、`PE_SOLUTION.md`、`EVALUATION_REPORT.md` | 🟢 |
| **② 隐式依赖**(动态/条件/反射) | 静态分析看不见,卡片会漏/会错 | 运行时 import、条件 import、反射、跨语言 FFI | humble prompt(承认卡片可能不全)+ 标注动态/条件 + 真实盲点定位 | humble 识破脏依赖 strict 7%→99%;真实盲点=dynamic/reflection(非 conditional,ast 抓得到) | `DIRTY_SCENARIO.md`、`DOWNSTREAM_HARM.md`、`DIRTY_MECH_RETRACTION.md` | 🟢 |
| **③ 长上下文**(信息在场仍丢) | 答案在场,上下文一长召回下滑 | 稀释 + 位置效应(非信息缺失) | 检索压缩到权威卡片 + 把权威信息放近问题端(recency) | 稀释衰减直接诊断(M66);位置细扫 recency 非 LITM、跨模型(M71 超额四) | `DIAGNOSIS.md`(M66 + M71 节) | 🟢 |

**对称性**:三瓶颈均【诊断+根因+靶向解+量化】齐全;**长上下文一栏由 M66 直接诊断补齐、M71 超额加深**,与前两栏对称。

---

## 二、PE 方案(要求:System / Few-shot≥20 / CoT / 后处理 四维度各独立量化)

| 维度 | 独立量化(判分无关/独立裁判) | 诚实定位 | 交付文件 | 状态 |
|---|---|---|---|---|
| **System Prompt** | 反幻觉约束把未接地文件名预测从 267→91(减 66%,M69 超额二);端到端独立裁判不显著 | 防幻觉真(源头预防),端到端增益边际 | `PE_SOLUTION.md`、`JUDGE_INDEPENDENT_VALIDATION.md` | 🟢 |
| **Few-shot(≥20)** | ≥20 例 few-shot 独立裁判不显著(在 RAG 主导下) | 边际(确认非杠杆) | `PE_SOLUTION.md`、`EXPERIMENTS.md` | 🟢 |
| **CoT** | 原 +0.02 经独立裁判证实是 self-judge 污染伪影,**已收回** | 边际/伪影(诚实撤回) | `M17_RESULTS.md`、`REBUTTAL_OR_FIX.md` | 🟢 |
| **后处理(过滤·排序·去重·补全)** | 排序(检索深度)+0.14;补全 +0.047 det-recall;去重 +0.034 精度;过滤本管线 Δ=0(上游 System 已防) | 排序是真杠杆;过滤 Δ=0 根因=预防>纠正(M69) | `PE_SOLUTION.md` §五(M64 + M69 节) | 🟢 |

**补齐说明**:**后处理维度由 M64 四维度审计补齐**(此前 PE 只报 System/CoT/Few-shot);M69 超额进一步解释了"过滤 Δ=0"的根因(源头预防 > 末端纠正)。

---

## 三、RAG 方案(要求:Pipeline / 混合检索 / 上下文管理 / 融合 / Recall@K·MRR / 端到端 + Embedding 选型)

| 环节 | 证据 | 交付文件 | 状态 |
|---|---|---|---|
| **Pipeline 完整** | chunk→embed→lexical→rerank→上下文组装,代码+配置实存 | `src/repomind_lab/`、`configs/*.yaml` | 🟢 |
| **混合检索** | 结构化卡片 + BM25 + 交叉编码器 rerank | `EVALUATION_REPORT.md`、`GRAPH_REPRESENTATION.md` | 🟢 |
| **上下文管理** | 检索深度/层级(rerank 12→80)是第二杠杆 | `EVALUATION_REPORT.md` | 🟢 |
| **融合/多跳** | 传递闭包物化:间接依赖 0.40→0.99(B2);B3 完整图子图检索过度工程(劣于轻量物化) | `GRAPH_REPRESENTATION.md` | 🟢 |
| **Recall@K / MRR** | werkzeug Recall@K 0.58→0.79、MRR 0.44→0.76;工业级 1456 池捕获 97.5% | `EVALUATION_REPORT.md`、`SCALE_STRESS_TEST.md` | 🟢 |
| **端到端** | 8 格消融 baseline 0.05→full 0.94 | `EVALUATION_REPORT.md` | 🟢 |
| **Embedding 选型调优** | 发现一直用中文 bge(任务英文/代码),换 en→R@5 0.93;**rerank 把选错语言的代价压缩 ~11.3×**(M68 超额一) | `EVALUATION_REPORT.md` §3b/3c、`EMBEDDING_IMPACT_AUDIT.md` | 🟢 |

**补齐说明**:**Embedding 选型由 M65 补齐**(此前未审 embedding 语言匹配),M67 地基核查影响范围,M68 超额量化 rerank 对其的掩盖。

---

## 四、微调(要求:≥500 条 / QLoRA / 过拟合监控 / 评估)——达标且呈现为"证明为何边际"

| 要求 | 证据 | 交付文件 | 状态 |
|---|---|---|---|
| **≥500 条** | 538 条(werkzeug 隔离,gen≠eval) | `MODEL_CARD.md`、`04_数据/finetune_train.jsonl` | 🟢 |
| **QLoRA** | Qwen2.5-14B QLoRA r=16,adapter 实存可加载 | `MODEL_CARD.md`、`02_模型微调权重/` | 🟢 |
| **过拟合监控** | eval loss 0.034→0.0092 曲线;hard 桶回归 −0.067(p<0.0001) | `MODEL_CARD.md` | 🟢 |
| **评估** | 生成器 +0.04 冗余、检索器 −0.02、DAPT 无、RL 检索器 0.958<静态 1.000 | `RETRIEVER_FINETUNE.md`、`DAPT_NOTES.md`、`RL_RETRIEVER.md` | 🟢 |

**定位**:四要求全达标,**结论是"证明为何边际"**——微调对"注入依赖知识"投入产出极低(被 RAG 主导且冗余),诚实负结果。

---

## 五、消融(要求:六格矩阵 / 最优策略 / 适用边界 / 可复现)

| 要求 | 证据 | 交付文件 | 状态 |
|---|---|---|---|
| **六格矩阵** | 扩到 8 格(原 6 格 + baseline + RAG+FT);工业级 1456 池复测保持 | `EVALUATION_REPORT.md`、`EXPERIMENTS.md` E50 | 🟢 |
| **最优策略** | best_stack(结构化卡片 + BM25 + rerank=80) | `EVALUATION_REPORT.md`、`configs/best_stack*.yaml` | 🟢 |
| **适用边界** | 静态可算→碾压;算不出(宏/动态/隐式链接)→退化;超大规模需分层 | `VALUE_FOR_REPOMIND.md` §3、`HONEST_LIMITATIONS.md` | 🟢 |
| **可复现** | 配置+脚本实存,mock 无 GPU 重建索引;核心结论 `verify_finding.py` 一键复算 | `06_开发者真值发现/verify_finding.py`、`README.md` | 🟢 |

---

## 六、超额项(非考题要求,标清"超额")— 详见 `BONUS_FINDINGS.md`

| 超额 | 一句话 | 复现 | 归档 |
|---|---|---|---|
| 一(M68) | rerank 把 embedding 选错语言的代价压缩 ~11.3×(MRR 差距 0.561→0.049) | `scripts/verify_bonus.py` M68 | `BONUS_FINDINGS.md` §1 |
| 二(M69) | 源头预防(System)未接地预测 267→91 减 66% > 末端纠正(filter Δ=0) | `scripts/verify_bonus.py` M69 | `BONUS_FINDINGS.md` §2 |
| 三(M70) | det-recall vs LLM-judge 双向分歧、互补(非谁取代谁) | `scripts/verify_bonus.py` M70 | `BONUS_FINDINGS.md` §3 |
| 四(M71) | 长上下文位置效应 = recency 非 LITM、跨模型、任务依赖性边界 | `scripts/verify_bonus.py` M71 | `BONUS_FINDINGS.md` §4 |

---

## 七、地基核查 + 诚实链 + 修复状态(终核)

| 项 | 状态 | 交付文件 |
|---|---|---|
| **地基核查(embedding 影响)** | A/B 分类 + 重跑 A 类:无方向翻转、一处幅度修正、机理澄清;B 类主线不受影响 | `EMBEDDING_IMPACT_AUDIT.md`、`HONEST_TRAJECTORY.md` §三C(第 15 次修正) | 🟢 |
| **诚实链** | 15 次有据自我修正(含 6 次亲手证伪自家漂亮解读) | `HONEST_TRAJECTORY.md` | 🟢 |
| **修复状态** | 17 行(评委指控 + 自查)全部标修复状态 + 指向 | `FIX_STATUS.md` | 🟢 |
| **候选清单** | 4 点全部标记"已做成超额"(grep 确认 4) | `INTERESTING_CANDIDATES.md` | 🟢 |

---

## 八、结论:逐条全绿,无空格

五道考题(瓶颈诊断/PE/RAG/微调/消融)**每一子项均 🟢**,各指向具体交付文件;四个超额项另行标清并可独立复现;地基/诚实链/修复状态终核通过。
**补考四空格(M64 后处理 / M65 Embedding / M66 长上下文诊断 / Few-shot≥20 确认)已全部补齐并入表。**
