# -*- coding: utf-8 -*-
"""FT-only 超参扫描(M73 核查):变 rank/lr/epoch,各自训练 LoRA 后 FT-only 评测 det gold-recall。
目的:确认 FT-only +0.043 是否近上限(真边际),还是单点超参没调到位。判分无关(keyword recall),无 LLM 裁判。
全程单卡 A800;每个 config 训练后立即 transformers 生成 56 题答案并打分,结果增量写 ft_sweep_results.json。"""
import json, os, gc, time, torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          DataCollatorForSeq2Seq, Trainer, TrainingArguments, EarlyStoppingCallback)

BASE = "<MODEL_DIR>/Qwen2.5-14B-Instruct"
TRAIN = "<REMOTE_WORKDIR>/ft/finetune_train.jsonl"
VAL = "<REMOTE_WORKDIR>/ft/finetune_val.jsonl"
BUNDLE = "<REMOTE_WORKDIR>/phaseA/bundle_werkzeug.json"
OUTJSON = "<REMOTE_WORKDIR>/ft/ft_sweep_results.json"
MAX_LEN = 1536
SYS = ("你是代码跨文件依赖分析专家。回答关于 werkzeug 项目的跨文件依赖问题,"
       "列出涉及的项目内模块文件名(每行一个文件)。只依据你掌握的知识作答,不要编造。")

tok = AutoTokenizer.from_pretrained(BASE)
if tok.pad_token is None: tok.pad_token = tok.eos_token
tok.padding_side = "left"

def encode(ex):
    msgs = ex["messages"]
    full = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    fi = tok(full, truncation=True, max_length=MAX_LEN, add_special_tokens=False)["input_ids"]
    pi = tok(prompt, truncation=True, max_length=MAX_LEN, add_special_tokens=False)["input_ids"]
    labels = ([-100] * len(pi) + fi[len(pi):])[:len(fi)]
    return {"input_ids": fi, "labels": labels, "attention_mask": [1] * len(fi)}

def load_ds(path):
    ds = Dataset.from_list([json.loads(l) for l in open(path, encoding="utf-8") if l.strip()])
    return ds.map(encode, remove_columns=ds.column_names)

TRAIN_DS, VAL_DS = load_ds(TRAIN), load_ds(VAL)
BUND = json.load(open(BUNDLE, encoding="utf-8"))

def load_base():
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    m = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map="auto",
                                             torch_dtype=torch.bfloat16)
    return m

def gen_and_score(model, tag):
    model.eval(); model.config.use_cache = True
    num = den = hnum = hden = 0.0
    answers = []
    for i in range(0, len(BUND), 8):
        batch = BUND[i:i+8]
        prompts = [tok.apply_chat_template([{"role": "system", "content": SYS},
                   {"role": "user", "content": b["question"]}], tokenize=False, add_generation_prompt=True)
                   for b in batch]
        enc = tok(prompts, return_tensors="pt", padding=True, truncation=True, max_length=2048).to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=400, do_sample=False, temperature=None, top_p=None,
                                 pad_token_id=tok.pad_token_id)
        for b, o, ln in zip(batch, out, enc["input_ids"]):
            txt = tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True).lower()
            golds = [g.strip().lower() for g in b["gold"].split(",") if g.strip()]
            r = sum(1 for g in golds if g in txt) / len(golds) if golds else 0.0
            num += r; den += 1
            if b.get("difficulty") == "hard": hnum += r; hden += 1
            answers.append({"id": b["id"], "answer": txt[:500], "recall": round(r, 3)})
    return dict(tag=tag, recall=round(num/den, 4), hard_recall=round(hnum/hden, 4) if hden else None,
                n=int(den), n_hard=int(hden)), answers

def train_cfg(name, r, alpha, lr, epochs):
    model = load_base()
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(r=r, lora_alpha=alpha, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])
    model = get_peft_model(model, lora); model.config.use_cache = False
    args = TrainingArguments(output_dir=f"/tmp/sweep_{name}", per_device_train_batch_size=8,
        gradient_accumulation_steps=2, num_train_epochs=epochs, learning_rate=lr,
        lr_scheduler_type="cosine", warmup_ratio=0.03, bf16=True, logging_steps=20,
        eval_strategy="steps", eval_steps=15, save_strategy="steps", save_steps=15, save_total_limit=1,
        load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
        report_to="none", gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False})
    tr = Trainer(model=model, args=args, train_dataset=TRAIN_DS, eval_dataset=VAL_DS,
                 data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
                 callbacks=[EarlyStoppingCallback(early_stopping_patience=3)])
    tr.train()
    evs = [h["eval_loss"] for h in tr.state.log_history if "eval_loss" in h]
    res, _ = gen_and_score(model, name)
    res["min_eval_loss"] = round(min(evs), 4) if evs else None
    res["cfg"] = dict(r=r, alpha=alpha, lr=lr, epochs=epochs)
    del model, tr; gc.collect(); torch.cuda.empty_cache()
    return res

CONFIGS = [
    ("base_noFT",   None, None, None,  0),     # 基线参考(无 adapter)
    ("r16_lr2e4_e3", 16,  32,  2e-4,   3),      # 复现原配置(应≈0.22-0.23)
    ("r32_lr2e4_e3", 32,  64,  2e-4,   3),      # 更大容量
    ("r64_lr2e4_e4", 64, 128,  2e-4,   4),      # 最大容量+多轮
    ("r16_lr3e4_e6", 16,  32,  3e-4,   6),      # 更高 lr + 更多 epoch
    ("r32_lr1e4_e6", 32,  64,  1e-4,   6),      # 低 lr 多轮(更充分收敛)
]

results = []
for name, r, alpha, lr, ep in CONFIGS:
    t0 = time.time()
    try:
        if r is None:
            m = load_base(); res, _ = gen_and_score(m, name)
            res["cfg"] = "base (no adapter)"; del m; gc.collect(); torch.cuda.empty_cache()
        else:
            res = train_cfg(name, r, alpha, lr, ep)
        res["sec"] = int(time.time() - t0)
        print(f"[DONE] {name}: recall={res['recall']} hard={res['hard_recall']} ({res['sec']}s)", flush=True)
    except Exception as e:
        res = dict(tag=name, error=str(e)[:300]); print(f"[ERR] {name}: {e}", flush=True)
    results.append(res)
    json.dump(results, open(OUTJSON, "w"), ensure_ascii=False, indent=1)

print("\n=== FT SWEEP SUMMARY (det gold-recall, judge-independent) ===", flush=True)
for r in results:
    if "error" in r: print(f"  {r['tag']:16} ERROR {r['error'][:80]}")
    else: print(f"  {r['tag']:16} recall={r['recall']:.4f}  hard={r.get('hard_recall')}  min_eval_loss={r.get('min_eval_loss')}")
print("ALLDONE", flush=True)
