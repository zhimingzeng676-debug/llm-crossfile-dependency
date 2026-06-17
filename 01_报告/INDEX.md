# INDEX — 交付物索引(给评审快速定位)

> 文档较多(过程留痕完整)。**核心可快速抽取——按下面三层读,不必被全部文档淹没。**

## ★ 阅读导航(分层,导师 5 分钟抓核心)

**第 1 层 · 先读这 3 个(看结论与观点):**
1. `INSIGHT.md` — 核心见解 / 论点 / 边界(项目灵魂)
2. `EXAM_COVERAGE_MATRIX.md` — 考题五大块逐条对照 → 对应文件 + 状态(评审入口)
3. `VALUE_FOR_REPOMIND.md` — 给甲方的决策语言(资源优先级)

**第 2 层 · 要看证据再读这些(量化 / 方案 / 关键验证):**
- 评测 / 消融:`EVALUATION_REPORT.md`、`EXPERIMENTS.md`(E1–E79)
- 三大瓶颈诊断:`DIAGNOSIS.md`;PE 方案(可复用):`PE_SOLUTION.md`;微调:`MODEL_CARD.md`
- 关键夯实验证:`CROSS_MODEL_GENERALIZATION.md`、`07_泛化夯实/STRONG_MODEL_VALIDATION.md`(前沿大模型)、`JUDGE_INDEPENDENT_VALIDATION.md`
- 可信度:`HONEST_TRAJECTORY.md`(诚实修正链,集中一处)、`FIX_STATUS.md`

**第 3 层 · 支撑 / 过程文档(其余):** 单专题深挖(脏依赖 / 下游危害 / 跨语言 / 图表示 / co-change 等)、对抗复审记录、各 `dayN.md` 里程碑任务单——按需查,**非必读**。

> 一句话路径:**INSIGHT → EXAM_COVERAGE_MATRIX → VALUE**(5 分钟)→ 需要证据再下钻第 2 层 → 专题/过程在第 3 层。

---

> 每份交付物一句话说明 + 它对应考核哪一项(下表为完整清单,可不通读)。

## 一、核心交付报告
| 文件 | 一句话 | 对应考核 |
|---|---|---|
| **EXAM_COVERAGE_MATRIX.md** ★ | 〔M72 收口〕考题验收对照表:五道考题(瓶颈诊断/PE/RAG/微调/消融)逐子项指向交付文件 + 状态全绿、无空格;补考四空格(后处理/Embedding/长上下文/Few-shot)已补齐入表 | 逐条核对·无空格 |
| **BONUS_FINDINGS.md** ★ | 〔M72 收口〕四超额项归档(非考题):rerank掩盖embedding 11.3×/源头预防>末端纠正减66%/det-recall vs judge双向分歧互补/位置效应recency非LITM跨模型;均判分无关、`verify_bonus.py` 一键复现 | 超额·可复现 |
| **DOWNSTREAM_HARM.md** ★ | M43新维度+M44做厚+**M45边界控制实验**:错卡片下游自信漏报89%危险>无卡片0%,跨4项目/2语言/3任务/2错法稳健(§3b);**§3f M46真实漏报下修、§3g M47言行脱钩证伪、§3h M48终审两硬伤已补(DANGER口径区间~1%~66%、公平对比下错卡片只略>无卡片+0.04~0.28)**;最终定论=真实但朴素、对着解析器真值、错卡片净负资产但增量modest | 真实价值·下游代价·口径区间·公平对比 |
| **MEMORY_VS_STRUCTURE.md** ★ | M42 记忆vs结构占比+私有代码迁移性:标识符全改名后结构化卡片100%保持(seen98.6→unseen100)、纯记忆仅17%→2%→碾压不靠模型背过代码、RAG预期干净迁移RepoMind私有代码;诚实定位=确认主线非新维度 | 甲方价值·迁移性·确认主线 |
| **DIRTY_MECH_RETRACTION.md** ★ | **M41 第10次自我修正(最严重)**:第六轮评委两指控成立——M38-40"喂源码补全90%"是挑口径(全样本42%→84.5%)+同源循环(58/58片段含答案,去循环76%)+机理被推翻(不喂源码靠记忆也74%);作废"信息可得性新发现",承认冲优秀压力下重犯挑口径+同源循环 | 诚实性·灌水自查 |
| **DIRTY_SCENARIO.md** ★ | M29脏场景退化+脏价值曲线;**M38-40 §9 humble识破脏依赖7%→99%(保留,硬)**;**§9.4 M41订正:识破≠补全/信息可得性/喂源码90%已作废(挑口径+同源循环+机理推翻)** | 真实价值·边界·订正 |
| **JUDGE_INDEPENDENT_VALIDATION.md** ★ | M36-37翻"墙一":核心结论零LLM确定性复算脱离裁判(数量级RAG det-recall 0.159→0.747 p=6.9e-12、humble脏识别20%→93%);校准集20→224;两处诚实下修(裁判宽松~0.2、humble只认性质不定位机制) | 评测可信度·脱离裁判 |
| **HONEST_LIMITATIONS.md** ★ | 三个已知局限直说(撤同源IRR旁证):人工IRR真空/实际靠单裁判Coder/baseline格式(M36-37:核心两结论已判分无关复算、不再受单裁判约束) | 诚实·局限 |
| **REVIEW_ROUND4.md** | 第四轮复审:升优秀(带条件)——脏场景实验真正面回应定义性软肋;脏/humble线证据偏薄需标方向性 | 对抗式复审 |
| **REVIEW_ROUND3.md** | 第三轮评委复审(良好持平+深层弱点) | 对抗式复审 |
| **VALUE_FOR_REPOMIND.md** ★ | 给RepoMind的价值主张(产品决策语言):资源优先级=结构化静态分析+检索深度>>模型/PE/微调/图RAG;可执行建议+边界 | 甲方价值·决策 |
| **IRR_AND_CALIBRATION.md** | 裁判可靠性诚实说明:κ=0.806是LLM裁判间(非人工IRR)、人工IRR未建立(已知局限)、裁判vs客观真值κ=0.941 | 评测可信度·诚实 |
| **REVIEW_GUIDE.md** ★ | 双评委导览:5分钟路线/结论→证据→验证→置信/可信度护栏/五交付物定位/怎么验证没造假 | 评审导览 |
| **INSIGHT.md** ★ | 核心见解(交付灵魂):核心论断+边界表+SOTA对标+独立观点(可信度是一等指标)+诚实自我修正历程 | 让交付有观点、不千篇一律 |
| **FINAL_REPORT.md** | 完整交付报告,逐条对齐五道题,结论先行+数据+负结果(已对齐 rerank=80 最新数据) | 五道题总览 |
| **PITCH.md** | 5 分钟答辩稿(六段)+ 12 个尖锐追问的有据回答 | 答辩 |
| **EVALUATION_REPORT.md** | 量化评测报告(独立):8格消融+三手段效应+检索质量+置信分级+跨项目泛化+边界 | 考核「量化评测报告」 |
| **EXPERIMENTS.md** | E1-E46(…E43 DAPT;**E44 独立裁判修复self-judge/收回CoT;E45 去循环金标准验证RAG;E46 图表示梯度;E49 B3子图检索=图RAG过度工程;E50 工业级六格消融保持;E51 RLCoder式RL检索器≤静态分析;E52 腾讯rapidjson旁证;E53 新工作去循环坐实**) | 所有题的数据支撑 |
| **RETRIEVER_FINETUNE.md** | 微调检索器记录(对比学习embedding,M14):隔离/训练/三层对照/结论(不是杠杆) | 微调·检索侧 |
| **DAPT_NOTES.md** | 领域自适应预训练记录(M15):SFT/DAPT/PEFT区分+遗忘监控+无增益结论 | 微调·穷尽性 |
| **REBUTTAL_OR_FIX.md** ★ | 外部评委三指控的逐条磁盘核实(self-judge/伪重复/评测循环):三条全成立→收回CoT、改配对统计、补IRR | 诚实性·对抗式自查 |
| **M17_RESULTS.md** ★ | M17 独立裁判修复闭环:三裁判(两家族)生成固定重判+deep n=15,CoT收回/RAG更硬/两LLM裁判间一致性 κ=0.806(LLM裁判间,非人工IRR) | 评测可信度·修复闭环 |
| **DECOUPLED_GOLDSET.md** ★ | M18 去循环金标准:ast独立重抽(与tree-sitter 100%吻合)+人工读源码,RAG去循环后+0.66~0.70仍铁(接住评委指控三) | 评测可信度·去循环 |
| **GRAPH_REPRESENTATION.md** | 现有"图表示"真实形态:后台真图、喂模型是1-hop节点邻接卡片文本投影 + M19图梯度(B2多跳物化救间接依赖) | 方法·图表示 |
| **RL_RETRIEVER.md** | M24-25 RLCoder式RL检索器:ppl弱监督有效(0.583→0.958)但≤静态分析(0.958<1.000),学习式检索器路径封口 | 微调·检索侧·穷尽 |
| **CROSS_LANGUAGE.md** ★ | M20跨语言泛化:Go/Java/C结构化表示全部数量级杠杆(+0.60~0.93,p<1e-6),论断升级"跨所测三语言(Go/Java/C)成立"(非Python特性) | 泛化·跨语言 |
| **SCALE_STRESS_TEST.md** ★ | M21工业级规模压力测试:CPython(3408文件/1456卡片池),结构化仍碾压(+0.89,p=1.5e-24)、检索未成瓶颈(rerank=80捕获97.5%)、跨语言Py↔C+1.00、工业级六格消融保持 | 泛化·规模 |
| **CONTAMINATION_AUDIT.md** | 历史评测污染审计(含 M15 原审计 + 顶部 M17 收回/修复声明) | 评测可信度·诚实性 |
| **CONFIDENCE.md** | 结论置信度审计:每条核心结论按样本量/方差/第二裁判/泛化分级(铁/较稳健/趋势性) | 答辩防追问·诚实性 |
| **DIAGNOSIS.md** | 分层归因诊断:排除统计/RAG实现/评测/模型四类混淆变量,再给"排除法后推论" | 答辩·为何 RAG 主导 |
| **DELIVERY_CHECKLIST.md** | 五样交付物逐一核对(以磁盘实文件/实跑为准)+ 缺口补救 | 交付前自检 |
| **RELATED_WORK.md** | 对标文献记录(arXiv 2505.15179 相似度检索)+ 本项目验证结论 | 答辩·文献对标 |
| artifacts/qwen14b-dep-lora/ | 微调 LoRA 权重本地存档(adapter 275MB + config + 训练曲线) | 交付物①实体 |
| docs/OFFICIAL_REQUIREMENTS.md | 考核原文存档 + 逐阶段自检表(全勾) | 对齐凭证 |

## 二、五道题的专项产出
| 考核题 | 主产出 | 关键数据 |
|---|---|---|
| ① 瓶颈诊断 | DATASET.md(56 用例选型/构造/难度)+ ERROR_ANALYSIS.md + EXP E14-E17 | baseline 0.27,四类瓶颈机理 |
| ② PE 优化 | **PE_SOLUTION.md**(四维度方案+模板+瓶颈→解法总表)+ EXP E21/E26 | CoT +0.03,领域 few-shot 0.81 |
| ③ RAG 管线 | EXP E1-E13(选型/混合检索/rerank 三部曲)+ E18 核心论证 | Recall 0.58→0.79,原始码 RAG<纯 LLM |
| ④ 模型微调 | **MODEL_CARD.md** + DATASET.md 隔离说明 + EXP E22-E24/E28 | FT +0.02 无增量出局(原 indirect −0.20 经 n=18 推翻) |
| ⑤ 消融实验 | EXP E25(六格矩阵)+ E27/E31(泛化)+ CONFIDENCE.md(分级) | 有无 RAG=铁结论;三格 0.77-0.80 噪声内持平 |

## 三、方法论与学习材料
| 文件 | 一句话 |
|---|---|
| LEARNING_NOTES.md | 47 条概念(RAG/embedding/rerank/LLM-judge/LoRA/过拟合/消融矩阵/统计方差/归因诊断…) |
| WORKLOG.md | 六天全过程日记(决策 1-25、每个负结果的诊断) |
| NEXT_STEPS.md | 收口后可选方向(检索瓶颈攻坚 / 更多泛化 / 接真 RepoMind) |

## 四、代码与数据(可复现)
| 路径 | 说明 |
|---|---|
| src/repomind_lab/ | 后端无关 RAG 库(切块/embedding/混合检索/rerank/别名解析/评测) |
| scripts/ | 全部脚本(数据集/PE/微调数据/裁判/可视化等) |
| scripts/remote/ | GPU 远端驱动(paramiko:部署 vLLM/训练/解耦评测) |
| configs/ | 所有实验配置(mock + werkzeug + 六格 + rich) |
| data/ | testcases_werkzeug(56)、testcases_rich(26)、finetune_train/val(538) |
| repos/ | werkzeug(测试)、flask/click/jinja2/requests(训练)、rich(泛化);均含 PROVENANCE |
| results/ | 全部评测结果 JSON + llmjudge_* + charts/ |
| models/ | bge-small-zh / bge-reranker-base(本地权重,curl 直下) |

## 五、复现说明(README.md「快速开始」)
- **无 GPU 核心链路**(已 M7 从零复现,逐位一致):解析器、数据集生成、
  werkzeug 检索 baseline(0.27/Recall0.58/MRR0.44)、mock 冠军(0.94/0.98)。
- **GPU 部分**(真 LLM / LLM-judge / PE / 微调 / 六格):README「真 LLM 评测(远端 GPU)」
  章节,paramiko 驱动 + 解耦评测,结果 JSON 已随包保存。

## 最终结论(一句话,M17 独立裁判修订)
**最优方案 = 全栈 RAG(依赖图卡片+混合检索+cross-encoder);PE/CoT 与微调经独立裁判均无可测正增益,出局。**
RAG 主导经**两独立家族裁判**坐实(deep 头条 0.915/0.954,p<1e-18);所有结论 LLM-judge(已校准,两LLM裁判间一致性 κ=0.806(LLM裁判间,非人工IRR))
+ 诚实负结果(含一次外审揪出、自己修复的 self-judge 污染)+ 瓶颈→解法适用边界齐全。
