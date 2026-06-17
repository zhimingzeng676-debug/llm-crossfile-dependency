"""解析代码仓库:输出函数/类/调用图/import 依赖/继承关系/常量。

用法:
    python scripts/parse_repo.py                       # 默认 mock_repo
    python scripts/parse_repo.py repos/werkzeug        # 真实项目
    python scripts/parse_repo.py repos/werkzeug results/werkzeug_graph.json
"""

import sys

from _common import PROJECT_ROOT

from repomind_lab.repo_parser import parse_repo, save_graph


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else str(PROJECT_ROOT / "mock_repo")
    repo_path = PROJECT_ROOT / repo if not str(repo).startswith(("/", "C:", "D:")) else repo
    graph = parse_repo(repo_path)

    print(f"仓库: {repo}  (包名: {graph.package_name or '(非包)'})")
    print(f"  文件 {len(graph.files)}  函数 {len(graph.functions)}  类 {len(graph.classes)}")
    print(f"  import 边 {len(graph.import_edges())}  继承边 {len(graph.class_edges())}  "
          f"调用边 {len(graph.call_edges())}  常量 {len(graph.constants)}")

    print("\n—— 跨文件继承样例(子类 -> 基类,基类在别的文件)——")
    cls_file = {c.name: c.file for c in graph.classes}
    shown = 0
    for sub, base in graph.class_edges():
        sub_file = next((c.file for c in graph.classes if c.name == sub), "?")
        if cls_file.get(base) and cls_file[base] != sub_file:
            print(f"  {sub} ({sub_file})  ->  {base} ({cls_file[base]})")
            shown += 1
        if shown >= 8:
            break

    out_arg = sys.argv[2] if len(sys.argv) > 2 else "results/repo_graph.json"
    out = PROJECT_ROOT / out_arg
    out.parent.mkdir(parents=True, exist_ok=True)
    save_graph(graph, out)
    print(f"\n完整结果已落盘: {out}")


if __name__ == "__main__":
    main()
