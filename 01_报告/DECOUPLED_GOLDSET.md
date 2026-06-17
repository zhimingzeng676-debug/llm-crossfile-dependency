# DECOUPLED_GOLDSET.md — 去循环金标准(M18 任务二,接住评委指控三)

> **评委指控三**:testcases 答案、RAG 卡片、裁判参考答案三者同出 tree-sitter,存在评测循环
> ("RAG 碾压"含"读回卡片"成分,幅度可能是同义反复)。
> **本文做法**:造一个**与项目 tree-sitter 管线完全解耦**的金标准,在其上用独立裁判复测 RAG 真实幅度。

## 1. 解耦方法(红线:gold 绝不来自生成卡片的同一管线)

金标准来源 = 两个**独立于 `repo_parser`/`load_graph_chunks`** 的渠道:

### 渠道 A:Python 标准库 `ast` 独立重抽(`scripts/build_decoupled_goldset.py`)
- `ast` 是与项目所用 tree-sitter **完全不同的解析器实现**(CPython 自带,不同代码库、不同算法)。
- 脚本**零 import** `repo_parser`/`chunking`,只用 stdlib `ast`,独立解析全部 52 个 werkzeug 源文件的
  import/类继承,自建相对 import 解析 + 反向边 + 包名归一化。
- **量化一致性(去循环的关键证据)**:归一化包名后,与 tree-sitter 金标准
  **forward_dep 67/67、reverse_dep 105/105、symbol_location 12/12 = 全部 100% 吻合**。
  → **两个独立解析器得出完全相同的依赖答案**,证明 gold 不是 tree-sitter 的臆造/伪影,而是源码客观事实。

### 渠道 B:人工读真实源码核验(难例,超越 1-hop 卡片"读回")
对 `ast` 1-hop 不足以独立确定、或需别名/传递推理的难例,**人工逐行读 `repos/werkzeug` 源码**确定答案:
| id | 类型 | 人工核验证据(读源码) |
|---|---|---|
| INH-07 | 别名继承 | `wrappers/request.py:20` `from ..sansio.request import Request as _SansIORequest` + `:31 class Request(_SansIORequest)` → 基类在 **sansio/request.py** |
| INH-08 | 别名继承 | `wrappers/response.py:16` `import Response as _SansIOResponse` + `:39 class Response(_SansIOResponse)` → **sansio/response.py** |
| IND-01 | 传递依赖 | `wrappers/response.py:9 from ..datastructures import Headers`(=datastructures/__init__.py)+ `datastructures/__init__.py:19-31` re-export `.mixins/.structures` → 传递中介 **datastructures/__init__.py** |
| IND-05 | 传递依赖 | 同上:response.py 直接 import 的是 datastructures 包(__init__.py),structures 由包二次分发 |

## 2. 去循环金标准构成(40 条)
| 类别 | 条数 | 金标准来源 |
|---|---|---|
| forward_dep | 11 | ast 独立(与 tree-sitter 100% 吻合) |
| reverse_dep | 13 | ast 独立(100% 吻合) |
| symbol_location | 12 | ast 独立(100% 吻合) |
| inheritance(别名) | 2 | 人工读源码 |
| indirect_dep(传递) | 2 | 人工读源码 |
**合计 40 条**,覆盖各依赖类型,难度有梯度。文件:`results/goldset_decoupled.json`。

## 3. 复测设计(隔离"评测循环"单一变量)
- **生成固定**:复用 M17 Phase B 已生成的 baseline / full_deep(rerank=80)**n=15 答案**,一字不改。
- **只换金标准**:把判分参考从 tree-sitter gold 换成本文的去循环 gold。
- **独立裁判**:Coder-14B + internLM2.5-7B(沿用 M17,gen=Qwen≠judge)。
- **统计**:40 条用例配对 t。
- **判定**:若 RAG 主效应(full_deep−baseline)在去循环 gold 下仍显著且幅度相当 → "评测循环"未制造 RAG 优势,
  评委最后一刀接住;若明显缩水 → 诚实报出循环贡献的部分与 RAG 真实幅度。

## 4. 结果(E45):RAG 主效应去循环后依然成立

同一批 Phase B 答案、同裁判,只把金标准换成去循环 gold(40 条配对):

| 裁判 | baseline | full_deep | **去循环 RAG主效应** | tree-sitter gold(M17) |
|---|---|---|---|---|
| 独立 Coder | 0.218 [0.209,0.228] | 0.916 [0.908,0.924] | **+0.698,p=9.8e-13** | +0.728 |
| 独立 internLM | 0.248 [0.235,0.260] | 0.908 [0.896,0.920] | **+0.660,p=1.7e-11** | +0.768 |

**判定:接住评委最后一刀。** 在与 tree-sitter 管线**完全解耦**的金标准上,RAG 主效应仍 **+0.66~+0.70(p<1e-10)**,
与 tree-sitter gold 的 +0.73~+0.77 **几乎一致**。"读回卡片/同源循环"贡献的部分 = 两者之差 ≈ **0.03~0.11**
(约占 ~0.7 效应的 **4~15%**),**已量化且很小**。→ **RAG 数量级主导不是评测循环的伪影,去循环后依然成立。**
(baseline 在去循环 gold 下略升 0.19→0.22~0.25,是独立 gold 对无 RAG 答案稍宽松,故 margin 略缩——如实呈现。)

## 5. 诚实边界
- 去循环只覆盖 RAG 主效应(有无依赖结构),未覆盖 deep CoT 等已收回结论(无需重验)。
- "读回卡片"的本质张力:依赖事实本身就是答案,提供它就是 RAG 的作用机制——
  去循环检验的是"**模型答对的是不是经独立验证的真实依赖**",而非取消"提供依赖=帮助"这一机制。
- inheritance/indirect 人工核验各仅 2 条(ast 独立性弱处),样本小,已如实标注;forward/reverse/symbol 是 100% 双解析器吻合的主体。
