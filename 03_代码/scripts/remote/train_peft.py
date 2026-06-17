"""M15:其他 PEFT 变体微调生成器(与 M5 LoRA 完全同口径,只换 PEFT 方法)。
同 538 数据 / 同隔离(werkzeug 零参与)/ 同超参基调。训练后合并进基座存为全模型(供 vLLM serve)。

用法(远端):python3 train_peft.py <dora|ia3>
"""

import json
import os
import sys

import torch
from datasets import Dataset
from peft import LoraConfig, IA3Config, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          DataCollatorForSeq2Seq, Trainer, TrainingArguments,
                          EarlyStoppingCallback)

METHOD = sys.argv[1] if len(sys.argv) > 1 else "dora"
BASE = "<MODEL_DIR>/Qwen2.5-14B-Instruct"
TRAIN = "<REMOTE_WORKDIR>/ft/finetune_train.jsonl"
VAL = "<REMOTE_WORKDIR>/ft/finetune_val.jsonl"
OUT = f"<REMOTE_WORKDIR>/ft/qwen14b-dep-{METHOD}"
MERGED = f"<MODEL_DIR>/qwen14b-{METHOD}-merged"
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
    return {"input_ids": full_ids, "labels": labels[:len(full_ids)], "attention_mask": [1] * len(full_ids)}


def load(path):
    ds = Dataset.from_list([json.loads(l) for l in open(path, encoding="utf-8") if l.strip()])
    return ds.map(encode, remove_columns=ds.column_names)


def peft_config():
    targets = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    if METHOD == "dora":
        # DoRA = 权重分解 LoRA(magnitude + direction),与 LoRA 同口径 r16/alpha32
        return LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                          task_type="CAUSAL_LM", target_modules=targets, use_dora=True)
    if METHOD == "ia3":
        # (IA)^3 = 学习的逐元素缩放向量(参数量远小于 LoRA),与之结构性不同
        return IA3Config(task_type="CAUSAL_LM",
                         target_modules=["k_proj", "v_proj", "down_proj"],
                         feedforward_modules=["down_proj"])
    raise ValueError(METHOD)


def main():
    train_ds, val_ds = load(TRAIN), load(VAL)
    print(f"[{METHOD}] train {len(train_ds)} val {len(val_ds)}")
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="auto",
                                                 torch_dtype=torch.bfloat16)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, peft_config())
    model.print_trainable_parameters()
    model.config.use_cache = False

    args = TrainingArguments(
        output_dir=OUT, per_device_train_batch_size=8, gradient_accumulation_steps=2,
        num_train_epochs=3, learning_rate=2e-4 if METHOD == "dora" else 1e-3,  # IA3 惯用更大 lr
        lr_scheduler_type="cosine", warmup_ratio=0.03, bf16=True, logging_steps=5,
        eval_strategy="steps", eval_steps=15, save_strategy="steps", save_steps=15,
        save_total_limit=1, load_best_model_at_end=True, metric_for_best_model="eval_loss",
        greater_is_better=False, report_to="none", gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False})
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                      data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
                      callbacks=[EarlyStoppingCallback(early_stopping_patience=3)])
    trainer.train()
    trainer.save_model(OUT)
    json.dump(trainer.state.log_history, open(os.path.join(OUT, "train_history.json"), "w"), indent=1)
    evs = [h["eval_loss"] for h in trainer.state.log_history if "eval_loss" in h]
    print(f"[{METHOD}] eval_loss: {[round(e,4) for e in evs]}")

    # 合并进基座存为全模型(fp16,供 vLLM serve;非 4bit)
    print(f"[{METHOD}] merging into base -> {MERGED}")
    del model, trainer
    torch.cuda.empty_cache()
    from peft import PeftModel
    base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float16, device_map="cpu")
    merged = PeftModel.from_pretrained(base, OUT).merge_and_unload()
    merged.save_pretrained(MERGED, safe_serialization=True)
    tok.save_pretrained(MERGED)
    print(f"[{METHOD}] DONE merged -> {MERGED}")


if __name__ == "__main__":
    main()
