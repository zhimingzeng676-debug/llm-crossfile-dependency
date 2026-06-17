"""构建 LLM-judge 校准集:20 条(配置,用例)样本 + 我的人工标注(锚定 ground truth)。
产出完整 judge-prompt(供远端裁判打分)+ 人工标注(供事后比对一致率)。

人工标注口径:对照数据集 notes(来自 tree-sitter 静态分析的可靠 ground truth),
答对正确文件/符号/关系=1,完全错/拒答=0,列出 N 个里对 k 个=k/总数。
"""

import json

from _common import PROJECT_ROOT
from repomind_lab.evalkit.testcase import load_testcases
from make_judge_prompts import JUDGE_TMPL, gold_points

# 我的人工标注(cfg|id -> 分),逐条读答案对照 ground truth 得出
HUMAN = {
    "purellm|LOC-01": 0.0,   # 答 wrappers/auth.py,错(应 datastructures/auth.py)
    "purellm|REV-07": 0.0,   # 拒答+瞎猜,无正确 importer
    "purellm|INH-07": 0.0,   # 幻觉 base_request.py/RequestMixin
    "purellm|FWD-03": 0.0,   # 拒答,无正确 dep
    "baseline|INH-08": 0.0,  # 诚实拒答,无答案
    "baseline|DAT-02": 0.0,  # "没找到"
    "graphcards|INH-07": 1.0,  # 正确:sansio/request.py 的 Request
    "graphcards|REV-02": 0.14, # 14 个里对 2(middleware/http_proxy, etag)
    "graphcards|FWD-10": 0.0,  # 拒答
    "graphcards|IND-01": 1.0,  # 正确:经 datastructures/__init__.py 间接
    "graphcards|LOC-04": 1.0,  # 正确:datastructures/file_storage.py
    "graphcards|INH-10": 0.2,  # 31 个里对 5
    "full|REV-07": 0.22,       # 18 个里对 ~4(formparser/etag/sansio.*)
    "full|INH-07": 1.0,        # 正确
    "full|FWD-10": 1.0,        # 8 个全对
    "full|LOC-01": 1.0,        # 正确 datastructures/auth.py
    "full|IND-05": 1.0,        # 正确:经 __init__.py 间接,非直接
    "full|INH-12": 0.5,        # 2 个里对 1(ContentSecurityPolicy,漏 _CacheControl)
    "full|REV-11": 1.0,        # 9 个全对
    "full|DAT-02": 1.0,        # 正确 debug/repr.py
}


def main():
    cases = {c.id: c for c in load_testcases(PROJECT_ROOT / "data" / "testcases_werkzeug.jsonl")}
    R = PROJECT_ROOT / "results"
    # 用全名还原 cfg
    cfgmap = {"purellm": "werkzeug_purellm_general", "baseline": "werkzeug_baseline_general",
              "graphcards": "werkzeug_graphcards_general", "full": "werkzeug_full_general"}
    # 缓存各配置的答案与 prompt(question)
    ans_cache, q_cache = {}, {}
    for short, full in cfgmap.items():
        ans_cache[short] = {a["id"]: a["answer"] for a in json.load(open(R / f"answers_{full}.json", encoding="utf-8"))}
        q_cache[short] = {p["id"]: (p["question"], p["judge"]) for p in json.load(open(R / f"prompts_{full}.json", encoding="utf-8"))}

    judge_prompts, labels = [], []
    for key, human in HUMAN.items():
        short, cid = key.split("|")
        q, judge = q_cache[short][cid]
        jp = JUDGE_TMPL.format(question=q, gold=gold_points(judge),
                               notes=cases[cid].notes, answer=ans_cache[short][cid])
        uid = f"{short}|{cid}"
        judge_prompts.append({"id": uid, "prompt": jp})
        labels.append({"id": uid, "human": human})

    (R / "judgeprompts_calib.json").write_text(json.dumps(judge_prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    (R / "calib_labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"校准集 {len(judge_prompts)} 条:judgeprompts_calib.json + calib_labels.json")


if __name__ == "__main__":
    main()
