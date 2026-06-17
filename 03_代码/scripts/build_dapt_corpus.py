"""M15:构造 DAPT(领域自适应预训练)语料 —— 训练项目的代码,做无监督 next-token 继续预训练。
与 SFT 不同:无"问题→答案"对,纯代码文本让模型沉浸领域分布。**werkzeug 严格不含。**

用法:python scripts/build_dapt_corpus.py
输出 data/dapt_corpus.jsonl,每行 {"text": <一段代码>}。
"""

import json
import sys

from _common import PROJECT_ROOT

sys.stdout.reconfigure(encoding="utf-8")
# 隔离红线:排除 flask —— 它是建在 werkzeug 之上的框架,代码大量 import/引用 werkzeug API,
# 会把 werkzeug 的结构泄漏进 DAPT 语料。用与 werkzeug 无依赖关系的 click/jinja2/requests,
# 并对残留 werkzeug 提及做段级过滤。代价:DAPT 域少了最像 werkzeug 的 flask,但隔离绝对干净。
TRAIN_REPOS = ["click", "jinja2", "requests"]
HOLDOUT = "werkzeug"
WINDOW = 1500   # 字符窗口(轻量,约 ~400-500 token)
STEP = 1500


def main():
    chunks = []
    for repo in TRAIN_REPOS:
        rp = PROJECT_ROOT / "repos" / repo
        assert HOLDOUT not in str(rp)
        py = sorted(rp.rglob("*.py"))
        n0 = len(chunks)
        for f in py:
            if "test" in f.name.lower() or "/tests/" in str(f).replace("\\", "/"):
                continue
            try:
                code = f.read_text(encoding="utf-8")
            except Exception:
                continue
            if len(code) < 100:
                continue
            for i in range(0, len(code), STEP):
                seg = code[i:i + WINDOW]
                if len(seg) > 200 and "werkzeug" not in seg.lower():  # 段级过滤残留泄漏
                    chunks.append({"text": seg})
        print(f"  {repo}: +{len(chunks)-n0} 段 ({len(py)} py 文件)")

    out = PROJECT_ROOT / "data" / "dapt_corpus.jsonl"
    with open(out, "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    # 隔离核查
    leak = sum(1 for c in chunks if "werkzeug" in c["text"].lower())
    print(f"\n共 {len(chunks)} 段 -> {out}")
    print(f"训练项目:{TRAIN_REPOS};留出:{HOLDOUT}。含 'werkzeug' 字样的段:{leak}(注释里提及不影响,无 werkzeug 源码)")


if __name__ == "__main__":
    main()
