"""cross-encoder(bge-reranker-base)的加载自检。

用法:python scripts/check_reranker.py
检查:模型能加载;对"相关"句对打分显著高于"不相关"句对。
(下载方法同 embedding 模型:curl 直下 hf-mirror,注意**必须核对字节数**——
 我们实测过 curl 静默断流留下 307MB 半截文件、退出码却是 0 的坑;
 断点续传:curl -sL -C - --retry 8 --retry-all-errors -o <文件> <URL>)
"""

from _common import PROJECT_ROOT

MODEL_DIR = PROJECT_ROOT / "models" / "bge-reranker-base"
EXPECTED_BYTES = 1_112_206_140  # 远端 Content-Length,防半截文件


def main():
    st = (MODEL_DIR / "model.safetensors").stat()
    assert st.st_size == EXPECTED_BYTES, f"权重文件不完整: {st.st_size} != {EXPECTED_BYTES},请断点续传补齐"

    from sentence_transformers import CrossEncoder

    model = CrossEncoder(str(MODEL_DIR))
    query = "退款有什么时间限制?"
    docs = [
        "退款时间窗口:支付成功后 30 天内才允许退款(REFUND_WINDOW_DAYS)。",
        "手续费费率按货币区分:人民币 0.6%,美元 2.9%。",
    ]
    scores = model.predict([(query, d) for d in docs])
    print(f"相关句对得分: {scores[0]:.3f},不相关句对得分: {scores[1]:.3f}")
    if scores[0] > scores[1]:
        print("自检通过:相关 > 不相关,cross-encoder 可用。")
    else:
        print("警告:打分不符合直觉,谨慎使用。")


if __name__ == "__main__":
    main()
