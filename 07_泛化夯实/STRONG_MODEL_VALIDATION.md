# STRONG_MODEL_VALIDATION.md — 前沿大模型验主线(界定最大未控变量)

> **动机(回应评委第二条,最致命未控变量):** 所有"模型侧边际、瓶颈在检索"的结论,生成器此前全是 14B 级开源模型。评委质疑:这可能是**模型容量受限**的伪影,换前沿大模型(更强隐式推理)结论可能翻转。本文用前沿大模型在 **同一批 werkzeug 56 用例 + 同一 prompt** 上重做核心对比,正面界定这个变量。
> **红线:** judge-independent 主指标 + LLM-judge 辅,**双口径全报;0 self-judge**(判官 glm-5 与两个生成器都不同家族);不挑模型不挑口径;两种结果都接受。**API key 仅经环境变量,绝不入库。**

## 做法
- **前沿生成器(2 个,经 API)**:**deepseek-v4-pro**(DeepSeek V4,异族前沿)、**qwen3-235b-a22b-instruct**(Qwen3 235B MoE,**与主线 14B 同族但参数量约 17×**——直接检验"是不是 14B 容量不够")。
- **同一 prompt bundle**(`bundle_werkzeug_{baseline,full_general_deep,pe_cot_deep}`,即主线在 14B 上得出时的原始 prompt),仅换生成器。
- **条件**:baseline(无依赖卡片)/ full(+依赖图卡片,深检索)/ pecot(full+CoT)。FT 跳过(前沿模型不易微调,如实标)。
- **口径**:judge-independent det gold-recall(主)+ LLM-judge(辅,judge=glm-5,gen≠judge,0 self-judge)。脚本 `api_gen.py`/`api_judge.py`(key 从 `LINGYA_API_KEY` 环境变量读取)。

## 结果(双口径,werkzeug 56,全样本)

| 模型 | baseline det/judge | full(RAG) det/judge | pecot(PE+RAG) det/judge | **RAG 杠杆**(det/judge) | **PE 增量**(det/judge) |
|---|---|---|---|---|---|
| **deepseek-v4-pro**(前沿异族) | 0.213 / 0.04 | 0.982 / 0.96 | 0.965 / 0.93 | **4.6× / 26.8×** | −0.017 / −0.024 |
| **qwen3-235b**(前沿,~17× 大) | 0.205 / 0.18 | 0.982 / 0.95 | 1.000 / 0.96 | **4.8× / 5.4×** | +0.018 / +0.016 |
| Qwen2.5-14B(主线 14B 对照) | 0.287 / 0.18 | 0.885 / 0.96 | 0.940 / 0.96 | 3.1× / 5.4× | +0.055 / +0.000 |

## 诚实定论(头号定性"检索受限"——加固,非翻转)
**三个关键问题逐一回答:**

1. **前沿大模型的 baseline 是否显著高于 14B?→ 否,甚至略低。**
   前沿 baseline det **0.21**(deepseek 0.213 / qwen3 0.205)**不高于** 14B 的 0.287;LLM-judge 口径下前沿 baseline **更低**(deepseek 仅 **0.04**)。**一个比 14B 大约 17× 的模型(qwen3-235b)和一个前沿异族模型(deepseek-v4),在没有结构卡片时同样列不出跨文件依赖。** → **"模型容量受限伪影"被直接证伪**:不是 14B 不够大,是**这个结构事实本来就不在模型的参数知识里**(谁 import 谁是要算的,不是要记/猜的)。

2. **RAG 杠杆在前沿模型上是否仍是大效应?→ 是,且更大。**
   full(RAG)在两个前沿模型上 det 都到 **0.982**、judge **0.95~0.96**;RAG 杠杆 det **4.6×~4.8×**(比 14B 的 3.1× 更大)。**"检索受限"在前沿容量上不仅成立、还更强**(前沿模型更会用喂进来的结构)。

3. **PE 在前沿模型上是否仍边际?→ 是。**
   pecot−full 增量 det −0.017~+0.018、judge −0.024~+0.016,**全部在 ±0.06 内,两口径一致**。**PE 边际跨容量普适。**

**总结论:头号定性"代码跨文件依赖是检索/表示受限型任务、非模型能力受限"——经前沿大模型(含 ~17× 大模型)双口径验证,加固而非翻转。** 评委点名的最致命未控变量(14B 容量伪影)被正面顶掉:**容量不是瓶颈,结构信息缺失才是。**

## 边界(诚实)
- werkzeug 单项目 56 用例、单 temperature、n=1;judge 为单一独立模型(glm-5,gen≠judge,非多裁判投票)。
- 前沿模型经第三方 API 聚合服务(lingyaai),非官方端点;模型版本以服务商为准。
- deepseek 的 judge 杠杆 26.8× 是小分母(baseline 0.04)放大的方向性数字,真正信息量在"前沿 baseline 极低 + RAG 拉满"。
- FT 跨前沿模型未做(前沿不易微调);FT 边际/上限仅在 Qwen2.5-14B 验过(见 MODEL_CARD)。

**复现**:`api_gen.py`/`api_judge.py`(key 经环境变量)+ `sm_dual_scores.json`;bundle `sm_bundle_werkzeug_*`、答案 `sm_ans_*`、判分 `sm_judge_*`。
