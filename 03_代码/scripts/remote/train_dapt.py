"""M15 任务二:领域自适应预训练 DAPT(无监督继续预训练,与 SFT 性质不同)。
拿训练项目代码做 next-token 预测(无问题→答案对),让模型沉浸领域分布。
**轻量化红线**:LoRA-based 继续预训练 + 硬步数上限,够验证方向即可,绝不失控烧机时。
**隔离**:语料来自 click/jinja2/requests(已排除 flask 与 werkzeug),零 werkzeug。

用法(远端):python3 train_dapt.py
"""

import json
import os

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          DataCollatorForLanguageModeling, Trainer, TrainingArguments)

BASE = "<MODEL_DIR>/Qwen2.5-14B-Instruct"
CORPUS = "<REMOTE_WORKDIR>/ft/dapt_corpus.jsonl"
OUT = "<REMOTE_WORKDIR>/ft/qwen14b-dapt-lora"
MERGED = "<MODEL_DIR>/qwen14b-dapt-merged"
MAX_LEN = 1024
MAX_STEPS = 200   # 硬上限:轻量,够验证方向

tok = AutoTokenizer.from_pretrained(BASE)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token


def encode(ex):
    out = tok(ex["text"], truncation=True, max_length=MAX_LEN)
    return out


def main():
    rows = [json.loads(l) for l in open(CORPUS, encoding="utf-8") if l.strip()]
    assert all("werkzeug" not in r["text"].lower() for r in rows), "隔离红线:语料含 werkzeug"
    ds = Dataset.from_list(rows).map(encode, remove_columns=["text"])
    print(f"DAPT 语料 {len(ds)} 段(已核验 0 werkzeug);MAX_STEPS={MAX_STEPS}")

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="auto",
                                                 torch_dtype=torch.bfloat16)
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    model.config.use_cache = False

    args = TrainingArguments(
        output_dir=OUT, per_device_train_batch_size=4, gradient_accumulation_steps=4,
        max_steps=MAX_STEPS, learning_rate=1e-4, lr_scheduler_type="cosine", warmup_ratio=0.05,
        bf16=True, logging_steps=10, save_strategy="no", report_to="none",
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
    trainer = Trainer(model=model, args=args, train_dataset=ds,
                      data_collator=DataCollatorForLanguageModeling(tok, mlm=False))
    trainer.train()
    trainer.save_model(OUT)
    hist = [h for h in trainer.state.log_history if "loss" in h]
    json.dump(hist, open(os.path.join(OUT, "train_history.json"), "w"), indent=1)
    print("DAPT loss:", [round(h["loss"], 4) for h in hist])

    # 合并供 vLLM serve
    del model, trainer
    torch.cuda.empty_cache()
    base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float16, device_map="cpu")
    merged = PeftModel.from_pretrained(base, OUT).merge_and_unload()
    merged.save_pretrained(MERGED, safe_serialization=True)
    tok.save_pretrained(MERGED)
    print("DAPT DONE merged ->", MERGED)


if __name__ == "__main__":
    main()
