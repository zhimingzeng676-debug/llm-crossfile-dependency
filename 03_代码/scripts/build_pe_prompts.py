"""生成 PE 四维度的 prompt 配置(项目无关:System/CoT 模板不含 werkzeug;
Few-shot 用通用迷你项目示例教格式,可整体替换到别的项目)。

产出 configs/prompts/ 下:pe_system.yaml / pe_fewshot.yaml / pe_cot.yaml / pe_all.yaml。
"""

import yaml

from _common import PROJECT_ROOT

OUT = PROJECT_ROOT / "configs" / "prompts"

# ---- System Prompt:角色 + 输出格式约束(项目无关)----
SYSTEM = (
    "你是代码库跨文件依赖分析专家。回答依赖类问题时严格遵守:\n"
    "1. 只依据提供的[依赖图卡片]和代码片段作答,不使用记忆里的旧版本结构,不臆测;\n"
    "2. 上下文里没有的信息,明确说\"提供的信息中未包含\",绝不编造文件名/类名;\n"
    "3. 输出结构化:每条关系写成「文件路径 — 符号名 — 关系类型」;\"列出多个\"的问题\n"
    "   用编号列表逐条列全,不要只举几个例子;\n"
    "4. 遇到别名(import ... as)时,先把别名还原成它指向的真实模块/类,再回答。"
)

# ---- CoT:依赖推理模板(项目无关)----
COT = (
    "请先一步步分析再给结论:\n"
    "(1) 判断问题类型:正向依赖(我import谁)/反向依赖(谁import我)/继承/间接多跳/符号定位;\n"
    "(2) 在卡片与代码里定位相关实体;间接依赖要逐跳追中间节点;别名要先还原;\n"
    "(3) 逐条核对,把所有命中项列全(尤其反向依赖容易漏);\n"
    "最后用结构化列表给出结论。"
)

# ---- Few-shot 库(≥20):用通用迷你项目 demo/ 教格式与推理,不绑定 werkzeug ----
# 迷你项目设定:api/gateway.py, api/auth.py, core/models.py, core/store.py,
#               util/log.py, base/handler.py(项目无关示意)
FEWSHOT = [
    # forward_dep(3)
    ("在该项目中,api/gateway.py 直接 import 了哪些项目内模块?",
     "1. core/models.py — Order — 导入数据模型\n2. api/auth.py — verify — 导入鉴权\n3. util/log.py — log — 导入日志"),
    ("某文件 import 了 a.py 和 b.py,如何作答?",
     "逐条列出:1. a.py — 关系:import;2. b.py — 关系:import。只列上下文里确有的。"),
    ("core/store.py 依赖哪些内部模块?",
     "1. core/models.py — Record — import;若卡片显示无其它内部依赖,则只列这一条。"),
    # reverse_dep(4,强调列全 + 诚实)
    ("哪些文件 import 了 core/models.py?",
     "依据依赖图卡片\"被这些文件依赖\"一行,逐条列全:1. api/gateway.py 2. core/store.py 3. base/handler.py(卡片里有几个列几个,不遗漏)"),
    ("哪些文件依赖 util/log.py?(卡片列出 5 个使用方)",
     "逐条列全 5 个:1. api/gateway.py 2. api/auth.py 3. core/store.py 4. base/handler.py 5. core/models.py"),
    ("谁依赖 x.py?但上下文只检索到部分使用方。",
     "列出上下文中确有的使用方,并说明\"以上为提供的信息中出现的使用方,可能不完整\"。"),
    ("反向依赖问题模型容易漏列,怎么避免?",
     "以依赖图卡片的\"被依赖\"清单为准,逐项抄全,不要凭印象只举几个。"),
    # inheritance(4,强调别名还原)
    ("类 Child 继承自哪个文件的哪个类?卡片显示\"继承自 Parent [base/handler.py]\"。",
     "Child — 继承自 base/handler.py 的 Parent 类 — 关系:继承(跨文件)。"),
    ("类 Foo 的基类写作别名 _Base,如何作答?",
     "先还原别名:_Base 来自 `from core.models import Base as _Base`,即真实基类是 core/models.py 的 Base。Foo — 继承自 core/models.py 的 Base。"),
    ("哪些类继承了 Mixin?",
     "依据卡片\"继承它的子类\"逐条列全:1. A [m1.py] 2. B [m2.py]。"),
    ("某类多继承自 X 和 Y,如何作答?",
     "列出全部基类:该类同时继承 X 和 Y 两个类。"),
    # indirect_dep(3,多跳推理)
    ("A 是否间接依赖 C?路径经过哪个中间文件?",
     "逐跳追踪:A 直接 import B(中间节点),B 直接 import C → A 间接依赖 C,中间文件是 B 的完整路径。"),
    ("response 经包 __init__ 间接依赖 structures,是直接还是间接?",
     "response 直接 import 的是 包/__init__.py(包),structures 是经由包再分发的\"间接依赖\";中间文件是 包/__init__.py。"),
    ("如何判断 X 到 Y 是直接还是间接依赖?",
     "看 X 的 import 段:若直接出现 Y 则直接;若 X 只 import 了 Z 而 Z 再 import Y,则间接,中间节点是 Z。"),
    # symbol_location / dataflow(4)
    ("类 Widget 定义在哪个文件?",
     "Widget — 定义于 ui/widget.py(依据卡片\"定义位置\"行)。"),
    ("常量 MAX_SIZE 在哪个文件定义?",
     "MAX_SIZE — 定义于 core/config.py。"),
    ("函数 parse 定义在哪?",
     "parse — 定义于 util/parser.py。只给文件,不臆测行号除非卡片提供。"),
    ("符号定位题怎么保证准确?",
     "以卡片的\"定义位置\"或代码块的来源标注为准,不要根据命名习惯猜文件。"),
    # 诚实 / 格式(2)
    ("上下文没有相关信息时怎么回答?",
     "明确回答\"提供的信息中未包含该依赖关系\",不要编造或用旧版本记忆补全。"),
    ("回答依赖问题的统一格式是什么?",
     "每条写「文件路径 — 符号名 — 关系类型」;多项用编号列表;先结论后(可选)简短依据。"),
]


def fewshot_yaml():
    return [{"question": q, "answer": a} for q, a in FEWSHOT]


def write(name, system, few_shot, cot):
    data = {"name": name, "system": system, "few_shot": few_shot, "cot": cot}
    (OUT / f"{name}.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
    print(f"  configs/prompts/{name}.yaml  (few_shot={len(few_shot)} cot={cot})")


def main():
    fs = fewshot_yaml()
    write("pe_system", SYSTEM, [], False)
    write("pe_fewshot", SYSTEM, fs, False)
    write("pe_cot", SYSTEM, [], True)
    write("pe_all", SYSTEM, fs, True)
    print(f"Few-shot 库 {len(fs)} 条(≥20 达标)。")


if __name__ == "__main__":
    main()
