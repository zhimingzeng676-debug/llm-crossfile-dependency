"""下载/验证语义 embedding 模型(BAAI/bge-small-zh-v1.5)。

【实际蹚出来的路,记录在案】
1. pip 装 sentence-transformers:清华镜像 SSL 被掐,**阿里云镜像成功**:
   pip install sentence-transformers -i https://mirrors.aliyun.com/pypi/simple/
2. 模型权重:huggingface_hub(1.18)对 hf-mirror.com 做元数据校验会报
   "Distant resource does not seem to be on huggingface.co",设 HF_HUB_DISABLE_XET
   也没用 —— 但镜像的裸 HTTP 是通的。所以**绕开 hub 库,curl 直接下载**到
   models/bge-small-zh-v1.5/(PowerShell):

   $base="https://hf-mirror.com/BAAI/bge-small-zh-v1.5/resolve/main"
   $dst="models\\bge-small-zh-v1.5"
   New-Item -ItemType Directory -Force "$dst\\1_Pooling" | Out-Null
   foreach($f in @("config.json","model.safetensors","tokenizer.json",
       "tokenizer_config.json","vocab.txt","special_tokens_map.json","modules.json",
       "config_sentence_transformers.json","sentence_bert_config.json",
       "1_Pooling/config.json")){ curl.exe -sL -o "$dst\\$f" "$base/$f" }

本脚本现在的职责:检查本地模型在不在 → 加载 → 语义自检。
用法:python scripts/download_model.py
"""

from _common import PROJECT_ROOT

MODEL_DIR = PROJECT_ROOT / "models" / "bge-small-zh-v1.5"


def main():
    if not (MODEL_DIR / "model.safetensors").exists():
        print(f"本地模型不存在: {MODEL_DIR}")
        print("请按本脚本 docstring 里的 curl 命令下载(huggingface_hub 走镜像会被校验拦住)。")
        raise SystemExit(1)

    print(f"加载本地模型 {MODEL_DIR} ...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(MODEL_DIR))
    print(f"加载成功,向量维度 = {model.get_sentence_embedding_dimension()}")

    # 语义自检:相近句对的相似度应明显高于无关句对。
    # 这三句刻意用了"语义相关但用词不同"的组合 —— 这正是哈希词袋做不到的。
    sents = ["支付前的安全检查", "风控模块,检查黑名单", "计算手续费的费率"]
    vecs = model.encode(sents, normalize_embeddings=True)
    sim_close = float(vecs[0] @ vecs[1])  # 安全检查 ~ 风控
    sim_far = float(vecs[0] @ vecs[2])    # 安全检查 ~ 手续费
    print(f"自检:'安全检查'~'风控' = {sim_close:.3f},'安全检查'~'手续费' = {sim_far:.3f}")
    if sim_close > sim_far:
        print("自检通过:语义相近句对相似度更高,模型可用。")
    else:
        print("警告:相似度关系不符合直觉,谨慎使用。")


if __name__ == "__main__":
    main()
