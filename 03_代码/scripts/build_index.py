"""离线建索引:切块 -> embedding -> FAISS -> 落盘。

用法:
    python scripts/build_index.py configs/baseline.yaml
仓库或切块配置变了就要重建;只改 top_k / prompt 不需要重建。
"""

import sys

from _common import PROJECT_ROOT

from repomind_lab.config import ExperimentConfig
from repomind_lab.pipeline import build_index


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "configs/baseline.yaml"
    cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / config_path)
    stats = build_index(cfg, project_root=PROJECT_ROOT)
    print(f"[{cfg.name}] 索引构建完成")
    print(f"  总块数: {stats['n_chunks']}  (按类型: {stats['by_kind']})")
    print(f"  落盘位置: {stats['index_dir']}")


if __name__ == "__main__":
    main()
