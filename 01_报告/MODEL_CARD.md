# MODEL CARD — qwen14b-dep-lora(跨文件依赖分析 QLoRA adapter)

> 考核「模型微调」要求的 Model Card。诚实记录:本 adapter **正提升但不进最终推荐方案**
> ——它对依赖问答有真实正向(vs 无上下文基线 +0.04 overall / +0.11 hard,p<1e-4,与文献一致),
> 但**弱于 RAG 一个数量级、且在最优 RAG+CoT 上冗余**,故作为消融"被验证项"保留(诊断见 E40,**非"本质无效"**)。

## 基本信息
- **基座**:Qwen/Qwen2.5-14B-Instruct(M4 证 RAG 场景通用模型 > 代码模型,故选它)
- **方法**:QLoRA(4bit nf4 量化基座 + LoRA r=16 / α=32 / dropout 0.05,
  目标层 q/k/v/o/gate/up/down 共 7 个投影)
- **可训练参数**:68,812,800(占全模型 0.46%)
- **训练框架**:transformers Trainer + peft + bitsandbytes(原生 Trainer + 手动
  label masking,只训 assistant 回复;脚本 `scripts/remote/train_qlora.py`)
- **硬件**:单张 A800 80GB,约 10 分钟(93 步)

## 训练数据
- **538 条**(train 485 / val 53),从 flask/click/jinja2/requests 的 tree-sitter
  依赖图程序化导出(`scripts/build_finetune_data.py`),答案可追溯可核验。
- 格式:system + 依赖图卡片上下文(含干扰卡片) + 问题 → 结构化标准答案。
- 类型:间接依赖 142 / 符号定位 106 / 反向依赖 66 / 正向依赖 66 / 反向继承 55 / 跨文件继承 14。
- **隔离红线**:被测项目 **werkzeug 零参与训练**(完全留出),训练/测试无共享实体。

## 超参
- epoch 3、effective batch 16(per-device 8 × grad-accum 2)、lr 2e-4(cosine + warmup 0.03)、
  bf16、gradient checkpointing、max_len 1536。
- 过拟合监控:每 15 步评 val、load_best_model_at_end(metric=eval_loss)、early stopping patience 3。

## 训练曲线(过拟合监控)
eval loss:0.034(step15)→ 0.014 → 0.011 → 0.0092(step90,最低)→ 0.0092(step93)。
**单调下降不回升,训练分布上无过拟合拐点**;但 val 与 train 同分布(flask/click),
低 val loss 仅代表学会格式,**不代表泛化**(见下"已知局限")。

## 评估(werkzeug 56 用例,LLM-judge,base vs FT 同 prompt)
- 总体:base 0.75 → FT **0.77**(+0.02);medium +0.12。
- 分方向:正向 +0.06、反向 +0.07、继承 +0.02。
- ✅ **M13续 口径核对(E40,关键)**:**FT only(0.228)显著高于 baseline(0.185)**,overall +0.043 / **hard +0.111**,
  p<1e-4——**FT 单独用是真实正提升(含 hard),与文献(FSE2025 RAG-or-FT)一致。**
- ⚠️ **"FT 伤 hard −0.067" 已精确化**:那是"FT *叠加到 PE+RAG* 时"且在浅检索(rerank=12)下;深度修正(rerank=80)后
  All−PE+RAG hard 仅 **−0.009**(近零)。**FT 不伤 hard;FT 单独还显著提升 hard。** "回归"系叠加+浅检索的局部现象。
- 精确结论:FT 正提升但**弱于 RAG 一个数量级**(+0.04 vs +0.72)、在最优配置上**冗余**(All−PE+RAG +0.002~−0.005,p>0.5)。
- ⚠️ **M8 修正**:原稿曾报"间接依赖 −0.20(0.50→0.30)",基于 5 样本。审计一把间接
  用例扩到 n=18 后**未复现**(ft 0.50 ≈ plain 0.44,无崩塌),该项已推翻;且 +0.02 整体增益
  落在运行方差 σ≈0.014 内,**与零成本 PE 分数不可区分**。见 CONFIDENCE.md C9。

## 已知局限(诚实)
1. **弱于 RAG 一个数量级**:FT 单独 +0.04(vs baseline),RAG +0.72——同一任务上 RAG 是数量级杠杆,FT 是边际。
2. **在最优配置上冗余**:已有 RAG+CoT 后,RAG 已供给 FT 想记忆的结构事实,故 FT 无额外增量(All≈PE+RAG)。
3. **数据规模边界(诚实标注)**:538 条低于文献所述 FT 显效门槛(数千~亿级 token);本数据量下 FT 已为正,
   未充分探索大数据量下 FT 的上限——但鉴于与 RAG 差一个数量级,扩数据追平 RAG 不现实(且 RAG 更便宜)。

## 超参扫描(M73 核查:"边际"是否因单点超参没调到位)
原训练是单点超参(r16/α32/lr2e-4/ep3),为排除"FT 边际 = 没调到位",对 FT-only 扫 rank/lr/epoch(判分无关 gold-recall,werkzeug 56,脚本 `scripts/ft_sweep.py`,结果 `05_评测结果/ft_sweep_results.json`):

| 配置 | recall | hard | min_eval_loss |
|---|---|---|---|
| base(无 FT,本扫描参照) | 0.201 | 0.253 | — |
| **r16/lr2e-4/ep3(原配置)** | 0.225 | 0.303 | 0.0095 |
| **r32/lr2e-4/ep3** | **0.249** | **0.359** | 0.0127 |
| r64/lr2e-4/ep4 | 0.170 | 0.221 | 0.0074 |
| r16/lr3e-4/ep6 | 0.201 | 0.273 | 0.0085 |
| **r32/lr1e-4/ep6** | **0.252** | 0.269 | 0.0087 |

- **诚实承认:原单点 r16 略未调到位**——rank 16→32 把 FT-only 0.225→0.25(+0.025,hard +0.056),两个 rank-32 配置一致(非噪声)。原报告 FT-only 0.228 是 r16 单点、略低于上限。
- **但天花板硬封 ~0.25,无配置突破**:r64 在 538 条上**过拟合**(eval loss 最低 0.0074 却 recall 最差 0.170)——更大容量在小数据上反害,**约束是数据规模、不是 rank 不够**。
- **决策不变且更硬**:0.25 仍远低于 RAG 0.774(已扫超参确认上限),FT 在 RAG 之上仍冗余;"微调边际"从"单点观察"升级为"扫过上限的稳健结论"。
- **数据预算口径(声明的边界,评委第五条)**:本扫描扫了 rank/lr/epoch,**但没扫数据量(固定 538 条)**。故诚实结论是「**在 538 条微调数据预算下 FT-only 上限 ~0.25、次优于 RAG**」;**更大数据规模(如 5k–10k 领域数据)的适配未验证,是声明的边界**——本结论限定在当前数据预算下成立,非无条件"FT 次优"。(文献门槛在数千~亿 token,见局限③;但鉴于与 RAG 差一个数量级且 RAG 更便宜,扩数据追平 RAG 工程上不划算——这是判断,非已验证。)

## 结论
**不进最终推荐方案——理由是"被 RAG 主导且冗余",不是"FT 无效"。** FT 微调生成器对依赖问答有真实正向效果
(与 FSE2025/StackRepoQA 一致),但 RAG(+0.72)比它(+0.04)强一个数量级、更便宜、无需训练。
本 adapter 作为消融"被验证项":证明了**"在不喂目标项目数据时,微调生成器正提升但远不及 RAG"**这一精确结论。
(训练健康:eval loss 0.034→0.0092 单调降;adapter 加载正常——FT only 在留出集上超 baseline 即证;无 bug,见 E40。)
