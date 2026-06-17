# DATASET — werkzeug 跨文件依赖分析评测集

> 对应考核评分项「瓶颈诊断质量:用例基于真实项目/有明确答案/覆盖不同难度」。
> 这是评委检验"评测用例质量"的直接证据。

## 1. 为什么选 werkzeug 作为真实项目

选型标准(对口"跨文件依赖分析"方向):中小型、结构清晰、**跨文件依赖密度高**、
Python(便于 tree-sitter 解析)、famous(评委易核验)。候选对比:

| 候选 | 文件数 | 为什么没选 / 选它 |
|---|---|---|
| flask | 24 | 干净但偏小,跨文件依赖样例不够丰富 |
| requests | 18 | 太小,模块间关系简单 |
| rich | 78 | 偏渲染逻辑,依赖结构不如 web 框架清晰 |
| **werkzeug 3.1.8** | **52** | **入选** |

**werkzeug 入选理由**(每条都对应一类用例素材):
- **6 个子包交叉依赖**(routing / wrappers / sansio / datastructures / middleware / debug):
  `routing/map.py` 同时依赖 rules/matcher/converters/exceptions —— 正向依赖用例。
- **高扇入热点**:`http.py` 被 18 个文件依赖、`exceptions.py` 13 个 —— 反向依赖
  的 hard 用例(检索 top-5 装不下所有使用方,天然考"长上下文/跨文件关联")。
- **丰富的跨文件继承**:`exceptions.py` 里 38 个类(`HTTPException` 群)、
  `Request(_SansIORequest)`/`Response(_SansIOResponse)` 继承自 sansio 子包 ——
  跨文件继承用例,且含**别名继承陷阱**(见下,刁钻 hard)。
- **包级 re-export 间接依赖**:`datastructures/__init__.py` 把子模块符号再导出,
  形成 `A → datastructures/__init__.py → structures.py` 的间接依赖链 —— 多跳用例。

版本与可复现:werkzeug **3.1.8**,来源见 `repos/werkzeug/PROVENANCE.md`
(pip 版本号 = git release tag,等价可复现锚点)。

## 2. 用例构建方法:答案由静态依赖图导出,人来策划难度与问法

**核心原则:实体选择 + 难度 + 问法由人策划,标准答案由 tree-sitter 依赖图
程序化计算**(`scripts/build_werkzeug_dataset.py`)。这样:
- 答案**基于真实代码**、**可追溯到文件/行**(每条 notes 写明来源)、**可人工核验**;
- 不靠人脑记忆 52 个文件的依赖关系(易错),靠已验证的解析器;
- 改 werkzeug 版本或换项目,重跑生成器即可,用例不手工维护。

依赖图本身经过抽检核验(见 WORKLOG):`import_edges` 对照真实 import 语句、
`class_edges` 对照真实 `class X(Base)` 声明,逐条吻合。

## 3. 56 条用例的分布

> 共 **56 条**(≥50 达标),覆盖跨文件依赖的 6 个子类型 × 3 个难度。

### 按类型(对口考核要求的依赖子类型)
| 类型 | 数量 | 考察什么 | 标准答案来源 |
|---|---|---|---|
| forward_dep 正向依赖 | 11 | 某文件 import 了哪些项目内模块 | `import_edges` 出边 |
| reverse_dep 反向依赖 | 13 | 哪些文件 import 了某模块 | `import_edges` 入边 |
| inheritance 跨文件继承 | 12 | 类继承自谁/谁继承了它(跨文件) | `class_edges` |
| symbol_location 符号定位 | 12 | 某类定义在哪个文件 | 类定义表 |
| dataflow 数据流 | 3 | 某常量在哪个文件定义 | 常量表 |
| indirect_dep 间接依赖 | 5 | A→B→C 多跳依赖路径/中间节点 | import 图 BFS |

### 按难度(难度按依赖扇出/跳数自动定档)
| 难度 | 数量 | 定档规则 |
|---|---|---|
| easy | 18 | 单点事实:符号定位、常量定位、低扇出(≤2)依赖 |
| medium | 14 | 中扇出(3-6)依赖、直接跨文件继承 |
| hard | 24 | 高扇入(>6)反向依赖、多跳间接依赖、别名/多继承 |

**难度有效性验证**:baseline 上答案分随难度单调下降
(easy 0.47 → medium 0.24 → hard 0.14),证明难度标注真实拉开了差距,
不是随意贴标签。

## 4. 刻意设计的刁钻用例(隐式/间接依赖瓶颈点)

考核点名"隐式依赖忽略""跨文件关联断裂",这些是专门设计的 hard 靶子:

1. **别名继承陷阱(INH-07/08)**:`Request` 的基类在源码里写作 `_SansIORequest`,
   实为 `from ..sansio.request import Request as _SansIORequest`。问"Request 继承自
   哪个文件的哪个类",**静态名字 `_SansIORequest` 与真实类名 `Request` 不匹配** ——
   检索能同时拿到两个文件(recall=1),但结构链被别名切断。隐式依赖的教科书案例。
2. **多继承(INH-09)**:`BadRequestKeyError(BadRequest, KeyError)` —— 同时继承两个类。
3. **高扇入反向依赖(REV http.py / exceptions.py)**:18/13 个使用方,
   检索 top-5 装不下 —— 考"长上下文丢失"。
4. **包级 re-export 间接依赖(IND 系列)**:`wrappers/response.py` 经
   `datastructures/__init__.py` 间接依赖 `structures.py`,要求精确指出中间文件 ——
   多跳、单次检索拿不到中间节点。
5. **枚举类(INH-10)**:列出 HTTPException 的全部直接子类 —— 答案是一个集合,
   考抽取/生成的完整性。

## 5. 判定规则(沿用上阶段判定审计标准,避免假阳性)

- 主用 `keyword_all`(部分给分):答案需含的关键词 = 依赖文件名 stem / 类名。
- **关键词口径修正(诚实诊断)**:依赖类用例用**文件名 stem**(`structures`)而非
  全路径(`datastructures/structures.py`)做关键词 —— 因为真实代码是相对导入
  (`from .structures import`),用全路径当关键词会因"代码里根本没有全路径字符串"
  而误判为 0,污染瓶颈诊断。但**间接依赖**用例反过来要求精确全路径中间文件
  (`datastructures/__init__.py`):精确 ident 正是该类用例的考点,用 stem 会被
  同名 token 泄漏。这套口径在 WORKLOG 有完整推理。
- 每条用例的 `expected_sources` 指向证据文件,供 Recall@K / MRR 计算。

## 6. 已知的评测局限(诚实标注)

- **MockLLM 抽取式天花板**:M1-2 用抽取式 MockLLM 出 baseline,它对"枚举全部
  子类"(INH-10)、"中文问题↔英文代码"的语义对齐先天弱。**答案分是弱代理,
  M1-2 的严格信号是 Recall@K / MRR(纯检索,不经 LLM)**;真 LLM(M3)出真实答案质量。
- **Recall@K 的来源粒度**:reverse_dep 的 `expected_sources=[目标文件]`,衡量的是
  "目标的依赖卡片是否被检回";但答案也可由直接检索到 importer 文件满足 ——
  两种检索策略都合法,故 reverse_dep 的 recall 会略微低估真实可答性
  (与 ERROR_ANALYSIS 指出的文件粒度盲点同源)。
- **别名/re-export 未在解析器层解析**:INH-07/08 的别名、`__init__` re-export 的
  符号去向,当前解析器不追踪 —— 这既是真实项目的难点,也是后续(图增强/真 LLM)
  要攻克的瓶颈,已作为 hard 用例固化在集里。

---

# 微调数据集(M5)与测试集隔离(红线)

> 对应考核「微调数据集 ≥500 条」+ M5.md 的隔离红线。生成器:
> `scripts/build_finetune_data.py`,答案由 tree-sitter 依赖图程序化导出(可追溯可核验)。

## 规模与分布
- **538 条**(≥500 达标):train 485 / val 53(9:1,固定随机种子可复现)。
- 来源项目:**flask / click / jinja2 / requests**(都从 site-packages 复制到 repos/)。
- 类型分布(train):间接依赖 142、符号定位 106、反向依赖 66、正向依赖 66、
  反向继承 55、跨文件继承 14。**按 M5.md 要求,重点放了"间接依赖"这一难瓶颈**
  (从最初的 0 提到 142),并压低了最易的符号定位(从 302 限到 ~106)。

## 隔离方式(红线,绝无泄漏)
- **训练只用 flask/click/jinja2/requests;被测项目 werkzeug 整个留作测试集,
  零参与训练**。这是可能的最强隔离——训练与测试**没有任何共享的文件/类/实体**,
  56 条评测用例不可能泄漏进训练。
- 附带收益:这等于一个**泛化测试**——若微调(在 flask 等上学的格式/推理)能提升
  werkzeug 上的分数,说明模型学到的是**任务能力**而非记住了某项目;若没提升甚至
  下降,也是诚实可接受的结论(M5.md 的基调)。
- 训练样本格式与评测一致(system + 依赖图卡片上下文 + 问题 → 结构化答案),
  让"微调 vs PE"可比:两者教的是同一种"列全/别名还原/结构化"的行为。

---

## 微调检索器训练数据隔离(M14,RETRIEVER_FINETUNE.md)

- **来源**:对比学习三元组 `(查询, 正确依赖卡片, 难负卡片)` 仅从 flask/click/jinja2/requests 程序化生成
  (`scripts/build_retriever_data.py`),共 159 条。
- **红线**:被测项目 **werkzeug 零参与**(grep "werkzeug" 训练数据 = 0,已核验);跨项目验证集 rich 同样未参与训练。
- **负样本策略(影响效果,记录在案)**:① in-batch 随机负;② 显式难负 = 与正样本**同目录**的另一张卡片(语义近、答案错)。
- 这保证了 M14"微调检索器"结论(过度专化、略负)在**完全留出**的 werkzeug/rich 上测得,无泄漏。
