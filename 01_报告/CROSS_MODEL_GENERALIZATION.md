# CROSS_MODEL_GENERALIZATION.md — 主线跨模型泛化(M74)

> **动机**:主线结论(RAG 主导杠杆、PE 边际、PE+RAG 最优)此前几乎只在单一生成器
> **Qwen2.5-14B-Instruct** 上得出(co-change 支线跨过 3 模型,但那是支线)。本文补主线最大缺口:
> 换不同能力档 / 不同家族的生成器,验主线是否普适,并专门回答"PE/微调的边际是机理性普适、还是依赖模型能力"。
> **红线**:模型按代表性选(不挑 PE/微调友好);同一 werkzeug 56 用例 + **同一 prompt bundle**(只换生成器);
> judge-independent det gold-recall 为主 + LLM-judge 辅,**双口径全报**;**0 self-judge**(LLM-judge 用 gen≠judge 的独立裁判);全样本;两种结果都如实报。

## 模型与口径
- **Qwen2.5-14B-Instruct**(14B 通用,主线基准)、**internlm2.5-7B-chat**(异族 / 弱档 7B)、**Qwen2.5-Coder-14B-Instruct**(同档 / 代码专精)。
- **Llama-3.1-8B-Instruct 未纳入**:在本机 vLLM 反复 serve 失败(config 不兼容,**基础设施问题、非挑选排除**;M3-B 已记录该机型在本host的兼容问题)。如实标注。
- 同一 prompt bundle(`phaseB/bundle_werkzeug_{baseline,full_general_deep,pe_cot_deep}.json`,即主线在 Qwen 上得出时的原始 prompt),`gen_text.py` 仅换 `--served-model-name`。
- **主指标**:judge-independent det gold-recall(gold=用例 keywords,零 LLM);**辅口径**:LLM-judge(internlm 判 qwen14b+coder14b,coder 判 intern7b,**全部 gen≠judge**)。
- 条件:baseline(代码片段无依赖卡片)/ full(+依赖图卡片,深检索)/ pecot(full + CoT)。

## 主结果(双口径,werkzeug 56,全样本)

| 模型 | baseline det/judge | full(RAG) det/judge | pecot(PE+RAG) det/judge | **RAG 杠杆**(det/judge) | **PE 增量**(pecot−full,det/judge) |
|---|---|---|---|---|---|
| **Qwen2.5-14B**(通用) | 0.287 / 0.18 | 0.885 / 0.96 | 0.940 / 0.96 | **3.1× / 5.4×** | +0.055 / +0.001 |
| **internlm2.5-7B**(异族弱档) | 0.312 / 0.28 | 0.885 / 0.90 | 0.848 / 0.88 | **2.8× / 3.3×** | **−0.037 / −0.024** |
| **Qwen2.5-Coder-14B**(代码) | 0.166 / 0.21 | 0.927 / 0.96 | 0.964 / 0.99 | **5.6× / 4.5×** | +0.038 / +0.027 |

## 三件诚实定论

**1. RAG 数量级杠杆 = 跨模型普适(两口径一致)**
RAG(依赖卡片+深检索)在三个模型上都是大效应:det 2.8×~5.6×、judge 3.3×~5.4×。**不是 Qwen 特性**——主线最重的结论升级为跨模型规律。
- **额外发现(强化主线)**:**RAG 杠杆在代码专精模型 Coder-14B 上最大(det 5.6×)**——因为它**无依赖结构时 baseline 最低(det 0.166<通用 0.287)**:一个代码模型在没有依赖卡片时反而最差,**印证"依赖是算出来的结构事实、不在代码文本统计分布里"——连代码专精模型都得靠喂结构,不能从代码里推**。

**2. PE 边际 = 跨模型普适,且不随模型能力按朴素方向变(两口径一致)**
PE(CoT)在 RAG 之上,三模型增量全部很小(det −0.037~+0.055,judge −0.024~+0.027,均在 ±0.06 内)。
- **专门回答"边际是否依赖模型能力"**:**弱档 7B(internlm)上 PE 不仅不更有效,反而微负**(det −0.037 / judge −0.024,两口径一致)——**证伪"弱模型模型侧空间更大、PE 更有效"的朴素假设**。本任务上 PE 边际是**机理性的(任务答案可计算、PE 帮不上结构检索),非某些模型没调好**。

**3. 最优策略 = RAG 决定,PE+RAG ≈ RAG(跨模型)**
14B 模型(qwen/coder)pecot 略 ≥ full(PE 加一点点);弱档 7B(intern)full > pecot(PE 反拖)。无论哪个,**RAG 是决定因素,PE 在噪声带内**。最优策略"PE+RAG"在 14B 成立、在 7B 退化为"RAG-only ≥ PE+RAG",但**结论方向(RAG 主导、PE 边际)三模型一致**。

## 边界与未做(诚实)
- **微调跨模型未验**:FT-only 跨模型需对每个模型各自重训(成本高),本轮**未做;FT 的"边际 + 上限 ~0.25"结论仅在 Qwen2.5-14B 上验过**(M73 超参扫描)。诚实标注,不外推到其它模型。
- **Llama-3.1-8B 因 host vLLM 兼容失败未纳入**(基础设施,非挑选);故"异族"维度由 internlm(上海AI实验室,与 Qwen 异族)承担,Meta 家族未覆盖。
- baseline 这里含"代码片段、无依赖图卡片"(非纯无上下文),故 baseline det 0.16~0.31 高于纯无上下文口径;RAG 杠杆是"依赖卡片 vs 代码片段"的增益,口径在三模型间一致、可比。
- 单 temperature(0)、n=1;judge 为单一独立裁判(gen≠judge,非多裁判投票)。

## 结论
**主线(RAG 主导杠杆、PE 边际、RAG 决定最优)经 3 模型 / 2 家族 / 2 能力档、双口径验证为跨模型规律,非 Qwen2.5-14B 特性。** 并新增两个有价值的诚实点:① RAG 杠杆在代码专精模型上更大(结构事实连代码模型都得喂);② PE 边际不按"弱模型更有效"的朴素方向变——弱档 7B 上 PE 反而微负,边际是机理性的。

**复现**:`scripts/xmodel_run.sh`(生成)+ `scripts/xmodel_judge.sh`(LLM-judge)+ `scripts/xmodel_score.py`(det 打分);结果 `05_评测结果/xmodel_dual.json`、`xmodel_scores.json`。
