"""列出某配置评测结果里所有非满分用例的完整证据(误差分析的取数工具)。

用法:
    python scripts/list_errors.py                        # 默认看冠军配置
    python scripts/list_errors.py results/baseline.json
"""

import json
import sys

from _common import PROJECT_ROOT


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "results/best_stack_norerank.json"
    d = json.load(open(PROJECT_ROOT / path, encoding="utf-8"))
    imperfect = [c for c in d["cases"] if c["answer_score"] < 1.0]
    print(f"配置 {d['config_name']}:{len(d['cases'])} 条用例,非满分 {len(imperfect)} 条\n")
    for c in imperfect:
        print("=" * 70)
        print(f"{c['id']} [{c['category']}/{c['priority']}] 答案分={c['answer_score']} 检索命中={c['retrieval_hit']}")
        print(f"Q: {c['question']}")
        print(f"检索: {[r['chunk_id'] for r in c['retrieved']]}")
        print(f"判定: {c['answer_judge_detail']}")
        print(f"A: {c['answer'][:400]}")


if __name__ == "__main__":
    main()
