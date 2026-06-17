# 微调权重说明(权重文件未随仓库提交)

QLoRA adapter 权重 `qwen14b-dep-lora/adapter_model.safetensors`(约 263 MB)**超过 GitHub 单文件 100 MB 限制,未提交到仓库**(已被 `.gitignore` 排除)。

本目录保留 **adapter 配置**(`adapter_config.json` 等小文件)+ 本说明,完整规格见 `01_报告/MODEL_CARD.md`。

## 如何获取 / 复现权重
- **复现训练**(推荐):`03_代码/scripts/remote/train_qlora.py`(QLoRA r=16/α=32/lr2e-4/ep3,基座 Qwen2.5-14B-Instruct,数据 `04_数据/finetune_train.jsonl` 538 条)。超参扫描见 `03_代码/scripts/ft_sweep.py` + `05_评测结果/ft_sweep_results.json`。
- **如需权重文件本体**:请向作者索取(或经 Git LFS / 外部存储分发)。

## 重要结论(MODEL_CARD 详述)
微调对本任务**正提升但弱于 RAG 一个数量级、且在最优 RAG+CoT 上冗余**;超参扫描确认 FT-only 上限 ~0.25(rank-32 甜点,rank-64 在 538 条上过拟合反降),仍远低于 RAG 0.77。**故 adapter 作为消融"被验证项"保留,不进最终推荐方案——理由是成本/风险,非"无效"。**
