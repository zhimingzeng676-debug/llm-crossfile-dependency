"""单条提问(调试/演示用):看检索命中了什么、prompt 长什么样、答案是什么。

用法:
    python scripts/ask.py "process_payment 调用了哪些函数?"
    python scripts/ask.py "费率在哪配置?" configs/chunk_function.yaml
    python scripts/ask.py "..." configs/baseline.yaml --show-prompt   # 额外打印完整 prompt
"""

import sys

from _common import PROJECT_ROOT

from repomind_lab.config import ExperimentConfig
from repomind_lab.pipeline import RagPipeline, build_index


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_prompt = "--show-prompt" in sys.argv
    if not args:
        print(__doc__)
        return
    question = args[0]
    config_path = args[1] if len(args) > 1 else "configs/baseline.yaml"

    cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / config_path)
    # 索引不存在就自动构建(与 run_eval 行为一致):换配置提问不需要记得先 build_index
    if not (PROJECT_ROOT / cfg.index_dir / "index.faiss").exists():
        stats = build_index(cfg, project_root=PROJECT_ROOT)
        print(f"[{cfg.name}] 索引不存在,已自动构建({stats['n_chunks']} 块)\n")
    pipe = RagPipeline(cfg, project_root=PROJECT_ROOT)
    result = pipe.answer(question)

    print(f"配置: {cfg.name}")
    print(f"问题: {question}\n")
    print("—— 检索结果 ——")
    for i, rc in enumerate(result.retrieved, 1):
        print(f"  {i}. [{rc.score:.3f}] {rc.chunk.chunk_id}")
    if show_prompt:
        print("\n—— 完整 Prompt ——")
        print(result.prompt)
    print("\n—— 回答 ——")
    print(result.answer)


if __name__ == "__main__":
    main()
