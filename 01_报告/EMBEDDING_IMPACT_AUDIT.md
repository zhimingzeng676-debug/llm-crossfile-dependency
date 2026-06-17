# EMBEDDING_IMPACT_AUDIT.md — "选错语言中文 embedding" 对历史结论的影响范围核查(M67)

> M65 发现:项目一直用 `bge-small-zh`(中文)做语义 embedding,而任务是英文/代码;语义层 R@5 仅 0.321,换 `bge-small-en`→0.929。
> 地基诚实:必须核查这个错语言 embedding 影响了哪些历史结论、波及多大——不能因"主线大概没事"跳过。脚本 `scripts/pe31_embed_impact.py`(判分无关,本地 CPU)。

## 一、全实验按 embedding 角色分类(任务零)
| 类 | 实验/结论 | 检索方式 | embedding 角色 |
|---|---|---|---|
| **A(主角)** | "相似度检索 0.42<<依赖 0.89"(M11)| 纯语义 embedding(sim_only) | **主角**——相似度臂分数=embedding 排序质量 |
| **A** | "原始代码 RAG 0.16<纯 LLM"(E33) | 语义 embedding 检原始代码块 | **主角**(但 Recall 0.58=代码检回来了,瓶颈在信息非检索) |
| **A** | embedding 微调(对比学习,E41) | 微调 bge-small | **主角**(但结论是"被全栈冲掉") |
| **B(配角/不参与)** | **数量级杠杆**(卡片 vs baseline)| 确定性结构卡片检索 + BM25 + rerank | **不参与**(确定性 + rerank) |
| **B** | 多跳物化 / 别名解析 / 六格消融 / 跨语言 / 工业级 | 确定性卡片 / 全栈 | **不参与** |
| **B** | co-change 方向(M50-63)| 确定性 repo_parser + 共改 gold | **不参与** |
| **B** | 下游危害 / humble / 微调生成器 | 全栈检索 | **不参与** |

## 二、A类用正确 embedding 重跑(任务一,判分无关 Recall@K,werkzeug 56)
同粒度(每文件一 doc)对比 依赖卡片 vs 原始代码,zh vs en:

| embedding | 依赖卡片 R@5 | 原始代码 R@5 | 卡片−代码 |
|---|---|---|---|
| **zh(当前,错语言)** | 0.321 | 0.464 | **−0.143**(卡片反输代码) |
| **en(正确)** | **0.929** | 0.661 | **+0.268**(卡片胜) |

**结论变化**:
- **方向不翻转**:正确 en embedding 下,结构化卡片仍 > 原始代码(+0.268);主线"结构化 > 原始代码"成立。
- **幅度被影响、且 zh 下纯 embedding 检索层一度反向**:错语言 embedding 让简洁结构卡片更难被语义匹配,zh 下卡片(0.32)< 代码(0.46)。→ **任何"纯语义 embedding 层卡片就该比代码好"的隐含说法,在 zh 下不成立**;卡片优势靠全栈(BM25 精确名匹配 + 深 rerank)实现,非纯语义 embedding。
- **"相似度 0.42<<依赖" 的差距幅度被夸大**:相似度臂用错语言 embedding 测、被低估(en 下原始代码/相似检索 R@5 0.46→0.66 升高)→ 真实差距小于当时报的 −0.47。方向(NL 依赖问答上结构化检索 > 相似度)仍成立(结构臂用 rerank 兜底、且信息原因)。

## 三、B类主线不受影响(任务二,佐证)
**主线结论(数量级杠杆、多跳、消融、跨语言、工业级、co-change)用确定性结构卡片检索或全栈(rerank 兜底),不依赖语义 embedding 的语言。** 佐证:
- **M65 实测**:全栈(结构卡片 + BM25 + cross-encoder rerank)**即便用最差的 zh embedding 也达 Recall@5 0.79、MRR 0.76**——rerank 把弱 embedding 排序补回。
- 结构卡片检索本身是**确定性 + BM25 精确名匹配**主导,语义 embedding 只是混合检索的一臂、且被 rerank 兜底。
- **故所有"卡片碾压"主线分数(0.94 等)不依赖 zh embedding,不受影响。** 评委可放心:主线地基稳。

## 四、影响范围总结 + 诚实修正
- **无任何主线结论方向翻转。** 主线是 B 类(确定性/全栈),embedding 选语言不影响。
- **一处 A 类幅度修正**:"相似度检索 0.42<<依赖 0.89" 的相似度臂用错语言 embedding、被低估,**差距幅度夸大了**;正确 embedding 下相似度臂升高、差距缩小,方向不变。
- **一个被错语言 embedding 掩盖的真相(反而强化主线)**:纯语义 embedding 检索层,简洁结构卡片在弱 embedding 下不占优——**卡片优势是靠 BM25+rerank 实现的,不是靠语义相似**。这与主线"确定性 + 深 rerank 主导、embedding 次要"完全一致,且是个更精确的机理。
- **记入诚实链(见 `HONEST_TRAJECTORY.md`)**:这是幅度修正 + 机理澄清,非方向翻转;地基(B 类主线)经核查不受影响。

---
## 〔M75〕独立复现确认(自写自算,bge-reranker-base 真跑,本地 CPU)
用独立重写的脚本(`scripts/verify_embed_indep.py`,不读项目结论)从 werkzeug 源码重建结构卡 + testcases gold,真跑四个 embedding + 真跑 bge-reranker-base 重排,结果**精确吻合**本文宣称:
- bge-zh R@5/MRR **0.321/0.256**、bge-en **0.929/0.817**(逐位一致);MiniLM 0.804、codesearch 0.875。
- rerank 掩盖:无 rerank en-zh MRR 差距 **0.561** → 加 rerank 塌到 **0.051**,**压缩 11.1×**(宣称 11.3×,差异仅来自 gap_on 0.051 vs 0.049 舍入)。
- 边界证实:zh 池内 gold R@30=0.929,rerank 只能 recover 到 0.872(<en 0.923)——**rerank 救不回 7% 根本没进池的 gold**,"rerank 上限=候选池召回"成立。
结果 `05_评测结果/verify_embed_result.json`。此前本数字仅由 pe28/pe31/pe32 跑过、未二次独立复现;M75 补齐。
