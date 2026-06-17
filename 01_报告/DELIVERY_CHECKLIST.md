# DELIVERY_CHECKLIST.md — 五样交付物核对(M10)

> 原则:**一切以磁盘实际文件与实际重跑为准,不以记忆/历史汇报为准**(项目中途有机器重启,
> 且此前两次发现"以为成立的结论是假象")。本次核对均实际打开文件 / 实际重跑确认。

## ⚠️ 本次核对暴露的"汇报≠现实"问题(诚实记录)
- **M9 汇报"GPU 已停",实为假象**:核对发现 `VLLM::EngineCore`(pid 8692)仍存活、占着 73GB 显存——
  此前 `pkill -f vllm` 因进程名是大写 `VLLM` 而漏杀。本次显式 kill 后显存归 0。
  → 印证 M10 基调:**汇报必须用实际状态复核**。已修正,GPU 现可正常使用。

## 五样交付物

### ① 微调权重 + Model Card —【齐全,1 处已补】
- **adapter 实存且可加载**:远端 `<REMOTE_WORKDIR>/ft/qwen14b-dep-lora/`
  `adapter_model.safetensors`(275,341,720 B)+ `adapter_config.json`(r=16)实际存在;
  本会话 vLLM `--lora-modules dep=...` **实测加载成功**(`/v1/models` 返回 `dep`)。
- **本地存档**:已 SFTP 拉一份到 `artifacts/qwen14b-dep-lora/`(防 GPU 主机临时性丢失)。
- **MODEL_CARD.md**:基座(Qwen2.5-14B-Instruct)/方法(QLoRA r16)/数据规模(538,werkzeug 隔离)/
  超参/训练曲线(eval loss 0.034→0.0092)/局限/"不进方案"诚实说明 —— **六项齐全**。
- 〔已补〕加入 M9 新证据:FT 在 hard 难度桶 **显著回归 −0.067(p<0.0001)**。

### ② PE 方案文档 —【齐全】
- **PE_SOLUTION.md**:四维度(System/CoT/Few-shot/后处理)各自独立效果数据;
  **含可直接复用的项目无关模板**(System Prompt 模板 / CoT 模板,§二/§三,复制即用);
  瓶颈→解法总表(§七)。他人可复用 ✓。
- prompt 配置实存:`configs/prompts/{plain,pe_cot,pe_system,pe_fewshot,pe_domain}.yaml`。

### ③ RAG 方案(配置+代码+检索质量报告)—【齐全,检索指标将并入评测报告】
- **代码**:`src/repomind_lab/`(chunking/embedding/lexical/pipeline/repo_parser + evalkit)实存。
- **配置**:索引→检索→rerank→上下文各环节 `configs/*.yaml` 实存(baseline/graphcards/full/best_stack…)。
- **检索质量 Recall@K / MRR**:已测——werkzeug **Recall@K 0.58→0.79、MRR 0.44→0.76**
  (EXPERIMENTS E14-E16);此前散在 EXPERIMENTS,M10 **已汇总进 EVALUATION_REPORT.md** 便于定位。

### ④ 量化评测报告 —【齐全,M10 整合】
- 既有:FINAL_REPORT.md(对齐五题)+ EXPERIMENTS.md(E1-E35)+ CONFIDENCE.md(置信分级)+ DIAGNOSIS.md(归因)。
- 〔M10 补〕**完整 8 格消融矩阵**(原 6 格补 baseline + RAG+FT)+ **EVALUATION_REPORT.md**(独立整合)。

### ⑤ 可复现实验包 —【齐全,实跑验证】
- README.md(M1-9 全流程)+ requirements.txt + configs/ + scripts/ 实存。
- **实际重跑验证(本会话)**:① `run_ablation.py configs/baseline.yaml`(mock,无GPU)**从零重建索引(32块)、
  跑通,答案分 0.74 / 检索命中 0.63**,与文档一致;② `dump_prompts.py` 重解析 werkzeug 56 用例确定性一致;
  ③ M9 分析脚本读存档数据重跑数值逐位一致。
- 小缺口(不影响复现):无 `pyproject.toml/setup.py`,靠 `scripts/_common.py` 注入 `src/` 路径——README 已说明。

## 总评
五样交付物**全部齐全**;M10 的两处补救:(a) 8 格矩阵补全(任务二),(b) 评测报告整合 + 检索指标汇总(任务四);
一处诚实修正:M9"GPU 已停"系漏杀进程的假象,已实测纠正。无"汇报说做了但磁盘上没有/跑不通"的项。

---

## M13 终验(交付前最后一次,以本会话实跑为准)— 全部打勾 ✅

| 交付物 | 状态 | 本会话核实 |
|---|---|---|
| ① 微调权重 + Model Card | ✅ | adapter 本地 275,341,720 B 实存;MODEL_CARD 六项全(含 M9 hard回归) |
| ② PE 方案文档 | ✅ | PE_SOLUTION 含可复用模板;PE 上限对标 SOTA(RELATED_WORK 2602.13890) |
| ③ RAG 方案(配置+代码+检索质量) | ✅ | src/repomind_lab 全;Recall 0.58→0.79/MRR 0.44→0.78;检索深度结论(E37-38) |
| ④ 量化评测报告 | ✅ | EVALUATION_REPORT(8格+三手段+置信+泛化+边界+新深度复查+自评估) |
| ⑤ 可复现实验包 | ✅ | **本会话从零重跑**:mock 端到端重建索引→0.74/0.63;werkzeug dump 确定性一致 |
| ★ 灵魂 | ✅ | INSIGHT.md(核心见解)+ RELATED_WORK(4 篇 SOTA 对标) |

**结论:五样交付物 + INSIGHT 全部就位,FINAL_REPORT/PITCH/EVALUATION_REPORT 已对齐 rerank=80 最新数据,
无残留旧数字(旧 0.80 矩阵均加注"深度修正→0.94,相对结论不变")。从零复现通过,可交付。**

---
## M26 终确认(为双评委审阅)
- 五样交付物齐全:① artifacts/qwen14b-dep-lora(adapter在)+MODEL_CARD;② PE_SOLUTION+configs/prompts;③ src/repomind_lab+EVALUATION_REPORT;④ EVALUATION_REPORT+EXPERIMENTS(E1-E52);⑤ src/scripts/data/README。
- 评委友好:**REVIEW_GUIDE.md**(导览)+ **VALUE_FOR_REPOMIND.md**(甲方价值)+ **REBUTTAL_OR_FIX.md**(外审三刀修复)。
- 可信度护栏:gen≠judge全程0 self-judge、两独立家族裁判两LLM裁判间一致性 κ=0.806(LLM裁判间,非人工IRR)、用例配对、去循环金标准。
- 复现:无GPU核心链路逐位一致;统计可复算(analyze_*.py读分数确定性重算)。
- 甲方旁证:腾讯rapidjson结构化+0.83(E52,诚实标开源≠私有)。
- 交付副本 D:\claude\49_交付\01_报告\ 51份.md全同步。**可交付可审阅。**
