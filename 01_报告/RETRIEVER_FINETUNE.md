# RETRIEVER_FINETUNE.md — 微调检索器记录(M14)

> 项目唯一空白的补完:此前只微调生成器,从未微调检索器。本文记录"对比学习微调 bge-small embedding"的
> 数据/训练/隔离/结论,对标 RLCoder(ICSE2025)。**一句话:微调检索器在本任务上不是杠杆,反而略负——
> 检索侧已被静态分析卡片 + 现成 embedding + BM25 + 深 rerank 近乎饱和。**

## 1. 数据隔离(红线,比微调生成器更隐蔽)

- **训练对来源**:仅 flask / click / jinja2 / requests 四个训练项目(`scripts/build_retriever_data.py`)。
- **werkzeug 零参与**:被测项目完全留出,训练数据 grep "werkzeug" = 0(已核验)。
- **数据规模**:159 个三元组 `(查询, 正确依赖卡片, 难负卡片)`。
- **负样本策略(记录)**:① in-batch 随机负(MultipleNegativesRankingLoss 自动);② 显式**难负**=与正样本同目录的另一张卡片
  (语义近但答案错)。难负显著影响对比学习效果,故记录在案。
- 查询类型:reverse_dep / forward_dep / inheritance / symbol_location(覆盖各依赖问法)。

## 2. 训练(本地 CUDA)

- 基座:bge-small-zh-v1.5;损失:MultipleNegativesRankingLoss(InfoNCE);3 epoch / batch16 / lr2e-5 / fp16。
- **对比损失单调降 2.26 → 0.21**(4.8s,本地 GPU)。`scripts/finetune_embedding.py` → `models/bge-small-zh-ft`。

## 3. 三层对照(只换检索器一个变量,口径与全项目对齐)

| 层 | 现成 bge | 微调 bge | 结论 |
|---|---|---|---|
| ① 纯向量 Recall@5/MRR(werkzeug) | 0.679 / 0.495 | 0.491 / 0.438 | **过度专化**:easy 0.89→0.22、hard 0.50→0.73,overall ↓ |
| ① 纯向量(rich 跨项目) | 0.615 / 0.637 | 0.519 / 0.479 | **跨项目一致**:easy 1.00→0.17、hard 0.50→0.89,overall ↓ |
| ② 全管线 Recall@5(rerank=80) | 0.9464 | 0.9464 | **被 BM25+rerank 冲掉**(完全持平) |
| ③ 端到端 LLM-judge(n=15) | 0.9356 | 0.9150 | **−0.021,p=0.003 略负** |

## 4. 结论与边界

- **微调检索器不是杠杆,反而略负**:纯向量过度专化(拿 easy 换 hard,整体降)、全管线冲掉、端到端略降。
- **横向对比两个微调杠杆**:微调生成器 +0.04(冗余于 RAG)、微调检索器 −0.02(过度专化)——**两个学习式模型侧微调都是边际/负**,
  真正的杠杆是非学习的**结构(依赖卡片,+0.5)+ 检索深度(rerank 12→80,+0.14)**。
- **与 RLCoder 的关系**:RLCoder 说"检索侧微调是更大杠杆",但口径不同(它微调检索器、用 RL+大数据、在通用补全任务上);
  本项目是最小可行对比学习 + 159 条窄数据 + 已近饱和(Recall 0.95)的强 baseline。**不矛盾,是任务/方法/数据规模不同。**
- **诚实边界**:本结论限于**最小可行版**;过度专化部分源于数据小而窄,更大/更均衡数据或 RL 训练**可能**改善(未探索)。
  但全管线 Recall 已 0.95、深 rerank 已主导,**embedding 微调的上行空间被强 baseline 压得很小**——
  这本身是"现成检索 + 静态分析已接近本任务检索上限"的有力证据。

**复现**:`build_retriever_data.py` → `finetune_embedding.py` → dump `werkzeug_vec_{base,ft}` / `werkzeug_pe_cot_deep_ft`
→ `compute_retrieval_metrics.py`(检索指标)+ `gen_multi`(LLM-judge)。详见 EXPERIMENTS E41。
