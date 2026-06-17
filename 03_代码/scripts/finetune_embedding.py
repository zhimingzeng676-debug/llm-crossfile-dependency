"""M14:对比学习微调 bge-small-zh embedding(微调检索器,对标 RLCoder)。
MultipleNegativesRankingLoss(InfoNCE):把 查询 与 正确依赖卡片 拉近、与难负/in-batch 负推远。
训练数据严格来自训练项目(werkzeug 零参与)。本地 CUDA 训练,小模型~分钟级。

用法:python scripts/finetune_embedding.py
输出:models/bge-small-zh-ft/
"""

import json
import sys

from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
    losses,
)

from _common import PROJECT_ROOT

sys.stdout.reconfigure(encoding="utf-8")


def main():
    rows = [json.loads(l) for l in open(PROJECT_ROOT / "data/retriever_train.jsonl", encoding="utf-8")]
    ds = Dataset.from_dict({
        "anchor": [r["query"] for r in rows],
        "positive": [r["positive"] for r in rows],
        "negative": [r["hard_neg"] for r in rows],
    })
    print(f"训练三元组:{len(ds)}(anchor/positive/hard-negative);in-batch 负样本自动")

    base = str(PROJECT_ROOT / "models/bge-small-zh-v1.5")
    model = SentenceTransformer(base)
    print(f"基座:{base}  device:{model.device}")

    loss = losses.MultipleNegativesRankingLoss(model)
    out = str(PROJECT_ROOT / "models/bge-small-zh-ft")
    args = SentenceTransformerTrainingArguments(
        output_dir=out,
        num_train_epochs=3,
        per_device_train_batch_size=16,
        learning_rate=2e-5,           # 小,防小数据过拟合
        warmup_ratio=0.1,
        fp16=True,
        logging_steps=5,
        save_strategy="no",
        report_to=[],
    )
    trainer = SentenceTransformerTrainer(model=model, args=args, train_dataset=ds, loss=loss)
    trainer.train()
    model.save_pretrained(out)
    print(f"微调完成 -> {out}")
    # 打印最后几步 loss
    hist = [h for h in trainer.state.log_history if "loss" in h]
    print("loss 轨迹(头/尾):", [round(h["loss"], 4) for h in hist[:3]], "...", [round(h["loss"], 4) for h in hist[-3:]])


if __name__ == "__main__":
    main()
