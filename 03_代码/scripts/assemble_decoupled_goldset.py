"""M18:组装最终去循环金标准 = 36条ast独立(与tree-sitter 100%吻合)+ 人工读源码核验难例。
红线:gold 全部不来自项目 repo_parser/tree-sitter 卡片管线。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ind = json.load(open(ROOT/"results"/"independent_gold_bundle.json", encoding="utf-8"))
cs = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT/"data"/"testcases_werkzeug.jsonl",encoding="utf-8") if l.strip() and not l.startswith("//")}

# (1) ast 独立 100% 吻合的 forward/reverse/symbol(去循环证据:两独立解析器concur)
clean = [o for o in ind if o["category"] != "inheritance"]

# (2) 人工读真实源码核验的难例(别名继承 + 传递依赖,超越1-hop卡片读回)
manual = [
 {"id":"INH-07","category":"inheritance","question":cs["INH-07"]["question"],
  "gold":"sansio/request.py","gold_kw":["sansio/request.py"],
  "notes":"人工核验 repos/werkzeug/wrappers/request.py:20 `from ..sansio.request import Request as _SansIORequest` + :31 `class Request(_SansIORequest)` → 基类在 sansio/request.py(别名解析)"},
 {"id":"INH-08","category":"inheritance","question":cs["INH-08"]["question"],
  "gold":"sansio/response.py","gold_kw":["sansio/response.py"],
  "notes":"人工核验 wrappers/response.py:16 `import Response as _SansIOResponse` + :39 `class Response(_SansIOResponse)` → sansio/response.py"},
 {"id":"IND-01","category":"indirect_dep","question":cs["IND-01"]["question"],
  "gold":"datastructures/__init__.py","gold_kw":["datastructures/__init__.py"],
  "notes":"人工核验 wrappers/response.py:9 `from ..datastructures import Headers`(=datastructures/__init__.py)+ datastructures/__init__.py:19-31 re-export .mixins/.structures → 传递中介=datastructures/__init__.py"},
 {"id":"IND-05","category":"indirect_dep","question":cs["IND-05"]["question"],
  "gold":"datastructures/__init__.py","gold_kw":["datastructures/__init__.py"],
  "notes":"同 IND-01:response.py 直接 import datastructures/__init__.py(包),structures 由包二次分发"},
]
gold = clean + manual
# judge_text 需要的字段:id, question, gold, notes
bundle = [{"id":g["id"],"question":g["question"],"gold":g["gold"],"notes":g["notes"]} for g in gold]
json.dump(bundle, open(ROOT/"results"/"goldset_decoupled.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
ids = [g["id"] for g in gold]
json.dump(ids, open(ROOT/"results"/"goldset_decoupled_ids.json","w",encoding="utf-8"))
import collections
print(f"去循环金标准:{len(bundle)} 条")
print("类别分布:",dict(collections.Counter(g["category"] for g in gold)))
print("ids:",ids)
