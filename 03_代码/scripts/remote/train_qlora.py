"""QLoRA 微调 Qwen2.5-14B-Instruct(在远端 A800 跑)。

稳健实现:bitsandbytes 4bit 加载 + peft LoRA + 原生 transformers Trainer +
手动 label masking(只训 assistant 回复),避开 trl 版本 API 不确定性。
监控 train/val loss(过拟合),保存 adapter + 训练历史(loss 曲线)。

用法(远端):python3 train_qlora.py
"""

import json
import os

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          DataCollatorForSeq2Seq, Trainer, TrainingArguments,
                          EarlyStoppingCallback)

BASE = "<MODEL_DIR>/Qwen2.5-14B-Instruct"
TRAIN = "<REMOTE_WORKDIR>/ft/finetune_train.jsonl"
VAL = "<REMOTE_WORKDIR>/ft/finetune_val.jsonl"
OUT = "<REMOTE_WORKDIR>/ft/qwen14b-dep-lora"
MAX_LEN = 1536

tok = AutoTokenizer.from_pretrained(BASE)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token


def encode(ex):
    msgs = ex["messages"]
    full = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    full_ids = tok(full, truncation=True, max_length=MAX_LEN, add_special_tokens=False)["input_ids"]
    prompt_ids = tok(prompt, truncation=True, max_length=MAX_LEN, add_special_tokens=False)["input_ids"]
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]
    labels = labels[:len(full_ids)]
    return {"input_ids": full_ids, "labels": labels, "attention_mask": [1] * len(full_ids)}


def load(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    ds = Dataset.from_list(rows)
    return ds.map(encode, remove_columns=ds.column_names)


def main():
    train_ds, val_ds = load(TRAIN), load(VAL)
    print(f"train {len(train_ds)}  val {len(val_ds)}")

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="auto",
                                                 torch_dtype=torch.bfloat16)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    model.config.use_cache = False

    args = TrainingArguments(
        output_dir=OUT, per_device_train_batch_size=8, gradient_accumulation_steps=2,
        num_train_epochs=3, learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.03,
        bf16=True, logging_steps=5, eval_strategy="steps", eval_steps=15, save_strategy="steps",
        save_steps=15, save_total_limit=2, load_best_model_at_end=True,
        metric_for_best_model="eval_loss", greater_is_better=False, report_to="none",
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                      data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
                      callbacks=[EarlyStoppingCallback(early_stopping_patience=3)])
    trainer.train()
    trainer.save_model(OUT)
    tok.save_pretrained(OUT)
    # 落训练历史(loss 曲线),供过拟合监控文档
    hist = trainer.state.log_history
    json.dump(hist, open(os.path.join(OUT, "train_history.json"), "w"), ensure_ascii=False, indent=1)
    print("DONE saved to", OUT)


if __name__ == "__main__":
    main()
