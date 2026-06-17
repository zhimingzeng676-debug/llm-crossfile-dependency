"""本地生成某配置下所有用例的 prompt(检索+组装,不调 LLM),供远端 GPU 批量生成。

解耦真 LLM 评测:本地做检索+prompt 组装+(之后)判定,远端只做生成。避开 SSH
隧道在批量请求下被重置的脆弱性,也最省机时。

用法:python scripts/dump_prompts.py configs/werkzeug_graphcards_qwen.yaml data/testcases_werkzeug.jsonl
输出:results/prompts_<配置名>.json
"""

import json
import os
import sys

os.environ.setdefault("LLM_API_KEY", "EMPTY")  # 让 ApiLLM 能构造(不连接)

from _common import PROJECT_ROOT

from repomind_lab.config import ExperimentConfig
from repomind_lab.evalkit.runner import build_index
from repomind_lab.evalkit.testcase import load_testcases
from repomind_lab.pipeline import RagPipeline
from repomind_lab.prompting import build_prompt


def main():
    config_path = sys.argv[1]
    cases_path = sys.argv[2] if len(sys.argv) > 2 else "data/testcases_werkzeug.jsonl"
    cfg = ExperimentConfig.from_yaml(PROJECT_ROOT / config_path)
    cases = load_testcases(PROJECT_ROOT / cases_path)

    if cfg.backend.type != "none" and not (PROJECT_ROOT / cfg.index_dir / "index.faiss").exists():
        build_index(cfg, project_root=PROJECT_ROOT)

    pipe = RagPipeline(cfg, project_root=PROJECT_ROOT)

    out = []
    for c in cases:
        retrieved = pipe.backend.retrieve(c.question, top_k=cfg.backend.top_k)
        prompt = build_prompt(c.question, retrieved, pipe.prompt_cfg)
        out.append({
            "id": c.id,
            "category": c.category,
            "difficulty": c.difficulty,
            "priority": c.priority,
            "question": c.question,
            "prompt": prompt,
            "retrieved_sources": [rc.chunk.source for rc in retrieved],
            "expected_sources": c.expected_sources,
            "judge": c.judge.model_dump(),
        })

    out_path = PROJECT_ROOT / "results" / f"prompts_{cfg.name}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{cfg.name}: {len(out)} 条 prompt -> {out_path}")


if __name__ == "__main__":
    main()
