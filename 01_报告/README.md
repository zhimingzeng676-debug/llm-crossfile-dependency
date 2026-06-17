# 代码分析领域效果优化(PE/RAG/微调)— 工程脚手架

> ⚠ **M17 更正(外部评委触发)**:旧主结果系 self-judge + 伪重复统计。经三裁判(含两独立家族)重判 + 56 用例配对修复:
> **CoT/PE 增益已收回**(独立裁判全不显著);**RAG 主导坐实更硬**(deep 头条独立裁判 0.915/0.954)。最优 = **全栈 RAG**。
> 详见 `REBUTTAL_OR_FIX.md` / `M17_RESULTS.md` / `EXPERIMENTS.md E44`。

腾讯 mini 项目"基于微调/PE/RAG 的代码分析领域效果优化",**冲中难度**,
主攻**跨文件依赖分析**。正式考核要求见 `docs/OFFICIAL_REQUIREMENTS.md`。
本仓库是后端无关的 RAG + 评测 + 消融框架:**前 4 夜在 mock 仓库上把方法论打磨完整,
M1-2 起迁移到真实开源项目(werkzeug)**。

> **当前阶段(M1-2 / M3-A / M3-B)。** werkzeug 3.1.8(52 文件)+ 56 条
> 跨文件依赖用例(分难度,见 `DATASET.md`)。
> - M1-2:真实 baseline 答案分 0.27 / Recall 0.58 / MRR 0.44;瓶颈诊断(E14-E16)。
> - M3-A:别名解析攻克 INH-07 符号失联(0→1.0);MockLLM 全栈 0.91(E17)。
> - **M3-B:真 LLM 上机(A800 80GB,vLLM)。** Qwen2.5-Coder-14B 四档
>   0.30→0.16→0.59→0.75,通用 Qwen2.5-14B 0.20→0.27→0.69→0.83。
>   **铁证:原始代码 RAG 比纯 LLM 还差,跨文件依赖必须喂结构化依赖图卡片**(E18);
>   代码模型只在参数记忆赢、加 RAG 后通用模型反超(E19)。
> - **M4:LLM-judge 校准(MAE 0.022/95% 一致)+ PE 系统优化。** keyword 对真 LLM
>   基本公平、对 MockLLM 过奖 ~0.10(E20);PE 四维度:**CoT 最有效(间接依赖
>   0.40→0.70),通用 Few-shot 反伤,反向依赖任何 PE 治不了(检索的锅)**——
>   "PE 管推理、RAG 管检索"(E21,`PE_SOLUTION.md`)。
> - **M5:QLoRA 微调(被验证项)。** 538 条数据(werkzeug 完全隔离),通用 14B
>   QLoRA,过拟合监控。**高质量负结果**:FT 仅 +0.02、与零成本 PE 不可区分,**微调不进最终方案**
>   (E22-E24,`MODEL_CARD.md`)。
> - **M6(收口):六格消融矩阵 + 泛化验证。** PE only 0.19/RAG only 0.77/PE+RAG **0.80**/
>   All 0.79(**FT 出局**);rich(风格迥异项目)0.66→0.73 规律一致。**最优 = RAG+PE,在所测项目上一致成立**(E25-E27)。
> - **M7:收尾交付。** FINAL_REPORT/INDEX/PITCH 终版,对齐考核五题,从零复现。
> - **M8:置信审计。** 四审计(样本量/方差/第二裁判/泛化)+ 分级,产出 `CONFIDENCE.md`、E28-31;
>   诚实软化噪声内结论、推翻"FT 砸间接(5 样本)"。
> - **M9:分层归因诊断。** 排除统计/RAG实现/评测/模型四类混淆变量,产出 `DIAGNOSIS.md`、E32-35。
>   **翻回 M8**:CoT 是小而真信号(+0.020 p=0.001,被粗判定低估 ~2×、跨家族复现);
>   证伪"强 RAG 喂答案"(退化卡片证)。**RAG 主导是任务内禀属性**。(注:M9 曾报"FT hard 回归 −0.067",M13续已精确化——见下)
> - **M10:交付物审计与补缺。** 五样交付物逐一核对(`DELIVERY_CHECKLIST.md`,以磁盘实文件/实跑为准,
>   adapter 本地存档 `artifacts/`);**消融矩阵补全到完整 8 格**(E36,补 baseline+RAG+FT,统一口径 n=15);
>   整合独立 `EVALUATION_REPORT.md`。新发现:PE 无 RAG 时有害、RAG+FT≈RAG only(FT 纯冗余)。
>   边际效应 RAG +0.614 / PE −0.026 / FT +0.028。诊断见 `EXPERIMENTS.md` E14-E36。瓶颈→解法见 `PE_SOLUTION.md` §七。
> - **M11:补相似度检索 + 挖出深度杠杆。** 对标 arXiv 2505.15179(`RELATED_WORK.md`)实现相似度检索对照(E37)。
>   ① **相似度检索单用 ≪ 依赖检索**(werkzeug 0.42 vs 0.89;rich 0.27 vs 0.91,跨项目一致)——文献(代码补全)不迁移到依赖问答;
>   ② **真改进**:`rerank_candidates` 12→80(一行配置),werkzeug 0.79→**0.94**、**反向依赖 0.70→0.95**(纯深度 +0.142,p<1e-6)——
>   全程被一个欠调超参压着的天花板;③ 自我纠错:"显式融合最优"被 deep-mixed 控制否掉,reranker 深池自适应即可。
> - **M12:新深度核心复查 + 自评估(Repoformer 式)。** ① 在 rerank=80 下复查核心结论(E38):
>   深度统一抬 ~+0.14,**RAG 主导/CoT 小而真/FT 出局/PE only<baseline 全部保持**——之前的相对结论不是浅检索伪影。
>   ② 自评估(E39,`RELATED_WORK.md` Repoformer):答前自评上下文是否足够,不足则诚实"信息不足"——
>   **无 RAG 下把幻觉率 79%→0.1%**,价值在可信度不在涨分(代价:好上下文过度 abstain −0.044)。
> - **M13:提炼核心见解(`INSIGHT.md`)+ 最终交付收尾。** 五样交付物全打勾,FINAL/PITCH/EVALUATION 对齐 rerank=80。
> - **M13续:微调负结果诊断(E40)。** 对标文献(FSE2025 RAG-or-FT)做口径核对——**FT only 显著高于 baseline
>   (+0.04/hard+0.11,p<1e-4),FT 是正提升不是无效**;旧"性价比为负/伤 hard"系口径不精确(把"强 RAG 之上无边际"误说成"有害"),已精确化:
>   **FT 弱于 RAG 一个数量级、最优配置上冗余,故不进方案**(与文献一致)。训练健康、adapter 正常、无 bug。诊断见 `EXPERIMENTS.md` E14-E40。
> - **M14:微调检索器(对比学习 embedding,补上唯一空白,对标 RLCoder)。** 159 三元组(werkzeug 零泄漏)微调 bge-small。
>   结果(E41,`RETRIEVER_FINETUNE.md`):**纯向量过度专化**(easy 崩 hard 升 overall↓,werkzeug+rich 跨项目一致)、
>   全管线被 BM25+深rerank **冲掉**(Recall 持平)、端到端 **−0.021 p=0.003 略负**。**微调检索器不是杠杆。**
>   **最终定论:两个学习式微调(生成器 +0.04 冗余、检索器 −0.02 过度专化)都边际/负;真杠杆=非学习的结构(+0.5)+检索深度(+0.14)。**
> - **M15:穷尽模型侧努力(其他 PEFT 变体 + DAPT 领域预训练)。** 同口径 n=15 base 裁判(E42/E43):
>   DoRA **0.160(反伤,<baseline)**、IA³ 0.208≈LoRA、DAPT **0.173 无增益**(p=0.099)、遗忘探针前后 12/12。
>   **穷尽确认:换 PEFT 方法、做无监督领域预训练,模型侧努力一律边际/无效——依赖是"算"出来的结构事实,不是"读"出来的统计规律。**
>   ⚠️ 本阶段评测曾被**多实例并发 + self-judge** 污染(DoRA 虚高 0.40→base判 0.160),已修复并做**全历史污染审计 `CONTAMINATION_AUDIT.md`**(历史清白)。

## 一、前期家底(mock 仓库,方法论打磨)

RepoMind 本体不可得,先在 mock 仓库把一切建好:**RAG 管道、自动评测框架、
消融实验、PE 实验台、代码解析工具**,全部接口化。三个阶段的进展:
- **第一阶段**:四接口抽象的链路用 mock 全部跑通,评测/消融框架就位;
- **第二阶段**:占位逐项兑现 —— 真语义 Embedding(bge-small-zh,本地权重)、
  调用图接入(图卡片)、混合检索(BM25+RRF)、rerank 架构、真 LLM 客户端
  (填 key 即用);评测集扩到 41 条。**最优配置:答案分 0.87 / 检索命中 0.93**
  (baseline 0.74 / 0.63);
- **第三阶段**(严谨与答辩):判定规则审计、RRF 权重扫参(修复 E3 负结果)、
  语义 rerank 实验(E9)、逐用例误差分析(`ERROR_ANALYSIS.md`)、敏感性检查、
  可视化三张图(`results/charts/`)、答辩稿(`PITCH.md`);
- **第四阶段**(cross-encoder 兑现):接入 bge-reranker-base 完成 rerank 四方对照
  (E11),常量卡修复常量盲区(E12/E13)。mock 冠军 best_stack_final 当时实测
  **0.96 / 0.98**(M1-2 的图卡片重构后微调到 0.94,见 EXPERIMENTS E16 注;
  baseline 0.74/0.63;41 条用例仅剩 2 条
  非满分,均为 mock 生成侧局限)。轻量场景(无 cross-encoder,毫秒级)
  用 best_stack_norerank(0.87/0.93)。

> 第一次读这个项目?建议顺序:本文件 → `docs/OFFICIAL_REQUIREMENTS.md`(考核口径)
> → `PITCH.md`(5 分钟版全貌)→ `DATASET.md`(真实项目用例集)→
> `LEARNING_NOTES.md`(概念扫盲)→ 跑快速开始 → `EXPERIMENTS.md`(E1~E16)→
> `ERROR_ANALYSIS.md` → `WORKLOG.md` → `NEXT_STEPS.md`。

## 快速开始

环境:conda 环境 `y`(Python 3.10,依赖已装好;新机器 `pip install -r requirements.txt`,
注意国内用阿里云源,见 requirements.txt 注释)。
以下命令都在项目根目录(`D:\claude\49`)运行,把 `python` 理解成
`& "D:\anaconda3\envs\y\python.exe"`。

```powershell
# 0.(可选)验证 mock 仓库本身能跑
cd mock_repo; python demo.py; cd ..

# 1. 验证本地模型可用(权重已在 models/ 目录,无需联网;缺失时脚本给下载命令)
python scripts/download_model.py     # 语义 embedding(bge-small-zh,95MB)
python scripts/check_reranker.py     # cross-encoder 精排(bge-reranker-base,1.1GB)

# 2. 建索引:切块 -> embedding -> FAISS 落盘 indexes/<配置名>/
python scripts/build_index.py configs/baseline.yaml

# 3. 问一个问题,看检索结果和回答(加 --show-prompt 可看完整 prompt)
python scripts/ask.py "process_payment 调用了哪些函数?"
python scripts/ask.py "luhn_check 是被哪个函数调用的?" configs/graph_cards.yaml

# 4. 跑评测:41 条用例自动打分,结果落 results/<配置名>.json
python scripts/run_eval.py configs/baseline.yaml

# 5. 消融实验:10 个配置全跑 + 自动生成对比报告 results/ablation_report.md
#    (含 2 个加载 bge 模型的配置,全程 1~2 分钟)
python scripts/run_ablation.py
#    第四阶段冠军配置(含 cross-encoder,单跑约 1 分钟):
python scripts/run_eval.py configs/best_stack_final.yaml

# 6. 解析仓库:tree-sitter 提取函数/调用图/import,落 results/repo_graph.json
python scripts/parse_repo.py

# 7.(第三阶段)深度分析与可视化
python scripts/sweep_rrf.py      # E8:RRF 权重扫参 -> results/rrf_sweep.md
python scripts/sensitivity.py    # E10:敏感性检查 -> results/sensitivity.md
python scripts/make_charts.py    # 柱状/雷达/热力图 -> results/charts/*.png
python scripts/list_errors.py    # 冠军配置非满分用例的完整证据(误差分析取数)
```

### 真实项目(werkzeug,M1-2)

```powershell
# 1. 解析真实仓库:函数/类/调用图/import 依赖/继承(repos/werkzeug 已就位)
python scripts/parse_repo.py repos/werkzeug results/werkzeug_graph.json

# 2. 生成 56 条跨文件依赖用例(答案由依赖图导出,可追溯)
python scripts/build_werkzeug_dataset.py        # -> data/testcases_werkzeug.jsonl

# 3. 真实项目 baseline(暴露瓶颈)+ 图卡片 + 全栈三档对照
python scripts/run_eval.py configs/werkzeug_baseline.yaml   data/testcases_werkzeug.jsonl
python scripts/run_eval.py configs/werkzeug_graphcards.yaml data/testcases_werkzeug.jsonl
python scripts/run_eval.py configs/werkzeug_full.yaml       data/testcases_werkzeug.jsonl
```

每条用例同时报告**答案分 / Recall@K / MRR**,并按方向和**难度**分组(见 run_eval 输出)。

### 真 LLM 评测(远端 GPU,M3-B)

本机不能直连 ssh,**全程 paramiko 驱动**(`scripts/remote/`;**凭据通过环境变量 `REMOTE_HOST`/`REMOTE_PORT`/`REMOTE_USER`/`REMOTE_PWD` 传入,不在代码中硬编码**)。评测**解耦**:本地检索+判定,远端只生成(避开 SSH 隧道在批量请求下被
重置的脆弱性,最省机时)。流程:

```powershell
# 1. 远端环境(A800 80GB,Ubuntu 容器):apt 装 pip → 装 vLLM → snapshot_download 下模型
python scripts/remote/probe_gpu.py          # 探测 GPU/环境
python scripts/remote/setup_env.py           # 装 pip + 后台下模型/装 vLLM
python scripts/remote/start_download.py       # (如需)用 snapshot_download 下 Qwen-Coder-14B
#   下载完成判据:DONE 标记 + 6 个完整 safetensors + 0 个 .incomplete(别信 du 大小)

# 2. 起 vLLM server(setsid 脱离 + 轮询 /v1/models)
python scripts/remote/start_vllm.py <MODEL_DIR>/Qwen2.5-Coder-14B-Instruct Qwen/Qwen2.5-Coder-14B-Instruct

# 3. 本地生成 prompt(检索+组装,无 GPU)→ 远端批量生成 → 本地判定
python scripts/dump_prompts.py configs/werkzeug_graphcards_qwen.yaml data/testcases_werkzeug.jsonl
python scripts/remote/run_remote_gen.py prompts_werkzeug_graphcards_qwen.json "Qwen/Qwen2.5-Coder-14B-Instruct"
python scripts/judge_from_answers.py werkzeug_graphcards_qwen

# 4. 跑完停 server 释放显存(GPU 计费,别空耗)
#    python scripts/remote/_run.py "pkill -f 'vllm serve'"
```

四档配置:`werkzeug_{purellm,baseline,graphcards,full}_qwen.yaml`(纯LLM / 原始代码RAG /
依赖卡片 / 全栈);换通用模型把 `_qwen` 换 `_general` 并 serve `Qwen2.5-14B-Instruct`。

### LLM-judge + PE(M4)

```powershell
# LLM-judge:校准(必须先做)→ 复核 baseline → 评 PE
python scripts/calib_build.py                       # 20 条人工标注校准集
python scripts/remote/run_remote_gen.py judgeprompts_calib.json "Qwen/Qwen2.5-14B-Instruct"
#   解析比对见 EXPERIMENTS E20(MAE 0.022 / 95% 一致才过闸)
python scripts/make_judge_prompts.py <config>       # 任意配置 -> 裁判 prompt
python scripts/remote/run_remote_gen.py judgeprompts_<config>.json "Qwen/Qwen2.5-14B-Instruct"
python scripts/parse_judge.py <config>              # -> results/llmjudge_<config>.json

# PE 四维度(项目无关模板,见 PE_SOLUTION.md)
python scripts/build_pe_prompts.py                  # 生成 pe_system/fewshot/cot/all 提示
python scripts/dump_prompts.py configs/werkzeug_pe_cot.yaml data/testcases_werkzeug.jsonl
python scripts/remote/run_remote_gen.py prompts_werkzeug_pe_cot.json "Qwen/Qwen2.5-14B-Instruct"
python scripts/postprocess.py werkzeug_pe_all       # 输出后处理维度(选择性补全漏列)
```

判定主指标 = LLM-judge(已校准),keyword/Recall/MRR 为辅助硬信号。

每一步预期输出已在 `WORKLOG.md` 各阶段记录,跑出来对不上就是环境出了问题。

接真 LLM(有 API key 时):`$env:LLM_API_KEY="sk-..."`,然后
`python scripts/run_eval.py configs/llm_api_template.yaml`(模板内有说明)。

## 项目结构

```
├── mock_repo/            假的"支付服务"项目 = 被检索的代码仓库
│                         (含跨文件调用链、深调用链、命名误导/注释不一致陷阱,见其 README)
├── models/               本地模型权重(curl 直下镜像):bge-small-zh-v1.5(95MB,
│                         embedding)+ bge-reranker-base(1.1GB,cross-encoder 精排)
├── data/
│   ├── testcases.jsonl   41 条评测用例(四方向,含 6 类陷阱 badcase;JSONL 可直接增删)
│   └── mock_commits.jsonl 伪造的提交历史 13 条(历史追踪方向的数据源)
├── configs/              实验配置(YAML)。baseline + 单变量变体 + best_stack 组合
│   └── prompts/          PE 实验台:plain / cot / fewshot_cot 三种 prompt 配置
├── src/repomind_lab/     核心库(模块地图见包 __init__.py,每个文件头有设计说明)
│   ├── chunking.py         切块:fixed 滑窗 / function 按函数切 / 调用图卡片
│   ├── embedding.py        Embedder 接口 + 哈希词袋 + bge 语义模型(已兑现)
│   ├── vector_store.py     VectorStore 接口 + FAISS 实现
│   ├── lexical.py          BM25 词法检索(自实现,~60 行)
│   ├── retrieval.py        ★ 检索后端接口:LocalRag / Hybrid / Reranking / RepoMind占位
│   ├── llm.py              LLM 接口 + 抽取式 Mock + ApiLLM(OpenAI 兼容,已兑现)
│   ├── prompting.py        配置驱动的 prompt 组装(System/Few-shot/CoT)
│   ├── pipeline.py         串联:问题 → 检索 → prompt → LLM → 答案
│   ├── repo_parser.py      tree-sitter:函数定义/调用图/import 依赖
│   └── evalkit/            评测框架:用例/判定器/跑分器/消融对比
├── scripts/              所有可执行入口(快速开始里的全部命令)
├── indexes/              建好的向量索引(生成物,可随时删除重建)
├── results/              评测结果 JSON + 消融/扫参/敏感性报告 + charts/ 图表(生成物)
└── 文档:PITCH(答辩稿)/ EXPERIMENTS(E1~E10)/ ERROR_ANALYSIS(误差分析)
        / WORKLOG / LEARNING_NOTES / NEXT_STEPS / tasks.md / task2.md / task3.md
```

## 核心设计:四个可替换的接口(第二阶段后的状态)

| 接口 | 已兑现的实现 | 还差什么 |
|---|---|---|
| `Embedder` | 哈希词袋 + **bge-small-zh-v1.5(真语义,本地权重)** | — |
| `VectorStore` | FAISS IndexFlatIP | 大仓库时换 IVF/HNSW |
| `RetrievalBackend` | LocalRag + **Hybrid(BM25+RRF)** + **Reranking 装饰器** | RepoMindBackend(等内网 API) |
| `LLM` | 抽取式 MockLLM + **ApiLLM(OpenAI 兼容)** | 一个 API key |

MockLLM 是"抽取式"的(从检索结果里挑证据行作答),所以**评测分数真实反映
检索质量**,消融对比是有意义的 —— 这是本项目最重要的设计决策(WORKLOG 决策 6)。

## 当前实验结论(41 用例 × 10 配置,详见 EXPERIMENTS.md)

| 配置 | 答案分 | 检索命中率 | 一句话结论 |
|---|---|---|---|
| baseline(40行块/哈希/top3) | 0.74 | 0.63 | 参照组 |
| 按函数切块 | 0.73 | 0.76 | 调用链强、常量弱,此消彼长 |
| +调用图卡片 | 0.83 | 0.78 | 反向查询全面救活,性价比之王 |
| 真语义 embedding | 0.82 | 0.78 | history/semantic 大涨,标识符短板暴露 |
| 混合检索(单用) | 0.72 | 0.76 | 检索升答案降:RRF 稀释强信号(E8 已修复) |
| 全家桶,无 rerank | 0.87 | 0.93 | 轻量冠军(毫秒级延迟) |
| + 词面 / 双塔 rerank | 0.83 / 0.78 | 0.85 / 0.93 | 两代错尺子,负优化(E5/E9) |
| **+ cross-encoder + 常量卡** | **0.96** | **0.98** | **现冠军 best_stack_final(E11/E13)** |

最值得读的是 `EXPERIMENTS.md` 里的 rerank 三部曲(E5 词面负 → E9 双塔负 →
E11 交叉编码正):两次负结果各自贡献一半的"为什么",第三次的成功是推导出来的。

## 常见操作

- **加一条测试用例**:在 `data/testcases.jsonl` 末尾照格式加一行 JSON,重跑 run_eval。
- **加一个实验配置**:复制 `configs/baseline.yaml`,改名 + 改一个变量,
  `python scripts/run_ablation.py configs/baseline.yaml configs/你的.yaml`。
- **换一种 prompt**:在 `configs/prompts/` 加 YAML,然后在实验配置里指向它。
- **重建索引**:删掉 `indexes/` 重跑 build_index(改了切块/embedding 配置后必须重建;
  run_eval 发现索引缺失会自动建)。
