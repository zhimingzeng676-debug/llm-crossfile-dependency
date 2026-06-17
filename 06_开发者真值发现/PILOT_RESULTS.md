# PILOT_RESULTS — 开发者真值(BugsInPy 共改)vs 静态可见性 · 纯描述

> 性质:**测量记录,不是结论。** 不写"这证明了X""这是新发现"。
> 所有判断(尤其 static_invisible 边里多少是真耦合 vs 噪声、那个比例意味着什么)
> 留给醒来后人工 + 协作AI 讨论(见末尾"需人工判断点")。
> 红线遵守:全样本不挑子集;多口径全报;judge-independent(确定性规则);
> 共改≠依赖(全文称"共改边");去噪报两版;异常不静默(youtube-dl 抓取失败已记录)。

数据/脚本:`p1_extract_cochange.py`(Phase1)、`p2_static_visibility.py`(Phase2);
原始落盘见 `out/`(带时间戳的 records / edges / edge_class / summary / log)。

---

## Phase 1:开发者共改 gold(全样本,本地 CPU,判分无关)

来源:BugsInPy 每个 bug 的 `bug_patch.txt`(开发者修复该真实问题时实际改的 diff)。
共改集 = 该 patch 触及的源码 .py 文件集合。**这是 git 历史派生的开发者行为信号,
生成机制与静态解析器(ast/tree-sitter)正交。** 测试文件已与源码分离(BugsInPy 本身分离 test_file)。

| 指标 | 值 |
|---|---|
| bug 总数 | 501 |
| patch 解析成功 | 501 |
| 含 ≥1 源码 .py 的 bug | 500 |
| **多文件源码修复 bug(≥2 源码 .py)** | **66(13.2%)** |
| **共改边(文件对)** | **157** |

源码 .py fan-out 直方图:`{0:1, 1:434, 2:49, 3:8, 4:6, 5:2, 8:1}`

**去噪两版(报两版,不藏)**:去噪规则 = 丢弃触及 >8 个源码 .py 的 bug(Herzig:tangled commit 捆绑无关改动)。
本数据最大 fan-out=8,**阈值未删任何 bug → untangled == raw**(66 bug / 157 边两版相同)。
诚实:在"源码 .py 粒度"上 BugsInPy 修复以单文件为主,无极端 tangling;但这也意味着
**共改边样本量小(157)**——见局限。

每项目分布(多文件 bug / 共改边):pandas 30/55、scrapy 1/28、keras 7/20、youtube-dl 9/14、
matplotlib 4/11、fastapi 1/6、thefuck 2/7、black 2/4、tornado 3/3、cookiecutter 1/3,其余 1/1,sanic 0/0。

---

## Phase 2:静态可见性分类(import 级,多口径,判分无关)

对每条共改边 (A,B),抓两文件在 fixed_commit 的原始内容,用 `ast` 解析 import 并解析模块名,
判 A 是否 import B 的模块(或反向)。

**口径定义**:
- strict = 精确模块 import(A 直接 import B 的确切模块,或反向)
- med = strict + 包前缀(import 了 B 模块的祖先包,或反向)+ 相对 import 解析
- loose = med + 文本引用(一方源码里出现另一方文件名 stem 作标识符)

| | strict | med | loose |
|---|---|---|---|
| **静态可见率** | 47.9% | 80.6% | 87.5% |
| **静态不可见率** | **52.1%** | **19.4%** | **12.5%** |

(分母 = 抓取成功的 144 边;13 条 youtube-dl fixed_commit 在 GitHub 已 404 不可抓,记为 fetch_failed,不计入率)

**静态不可见边子类型(med 口径,共 28 条)**:
- cross_dir_no_static_edge:14(跨目录、无静态边;含 matplotlib examples/tutorials↔lib 等文档/示例-库共改)
- dynamic_or_registry_hint:9(含 `__import__`/`importlib`/`getattr`/register/plugin 线索;
  典型:keras `tensorflow_backend`↔`theano_backend`↔`cntk_backend` 三后端实现互不 import、靠动态切换)
- same_dir_sibling_no_static_edge:5(同目录兄弟文件、无静态 import 边)

**可见边示例(抽查)**:PySnooper `pycompat`↔`tracer`(strict)、black `black.py`↔`blib2to3/pgen2/driver`(strict)、
keras `backend/*`↔`initializers`(med 包前缀)。

---

## ⚠ 关键诚实限定(每个数字都要带着读)

1. **这是 import 级 + 直接边代理,不是项目自己的 repo_parser 结果。** 项目的静态卡片
   用 tree-sitter 在**全仓**上还建继承/调用边;本 Phase2 只看两改动文件间的直接 import。
   → 本测量**可能低估静态可见**(漏掉调用/继承边)、即**可能高估"静态不可见盲区"**。
   **权威版静态可见性应在全 checkout 上重跑项目的 repo_parser**(server 阶段),再与此对照。
   所以 med 不可见 ~19% 是这个代理口径下的**上界**,不是定论。
2. 模块←文件映射由 patch 里的仓库根相对路径推导;example/tutorial/doc 路径(如 matplotlib `examples/...`)
   无法映射进包,会被算作 cross_dir 不可见——**这部分"不可见"部分是路径映射产物,不全是真盲点。**
3. 共改边样本小(157,去噪后不变);youtube-dl 13 边丢失。**统计上是小样本,跨项目细结论不可下。**
4. **共改 ≠ 依赖。** 一条共改边只说明"开发者修这个 bug 时一起改了这两个文件",
   不等于"两文件有依赖关系",更不等于"模型理解了依赖"。

---

## Phase E(扩样本):全 git 历史 evolutionary coupling(judge-independent)

按"先扩样本再做 task3"指示,用全 git 历史的共提交关联规则扩大共改边(脚本 `pe1_evo_coupling.py`/`pe2_evo_static_vis.py`)。

### E1 — evolutionary coupling 挖掘(17 项目,多口径全报)
- 部分克隆(`--filter=blob:none`)17 仓库;`git log --name-only` 取每提交源码 .py 集合。
- **提交封顶 30000/项目**(ansible/matplotlib/pandas/youtube-dl 触顶;如实记,是口径限制)。
- 去噪 = 丢弃触及 >T 源码 .py 的提交(tangling);关联规则 support≥S & confidence≥C。

**共改边数(tangle阈值 × 规则,全报)**:
| tangle≤ | S3_C0.3 | S5_C0.4 | S8_C0.5 | S10_C0.6 |
|---|---|---|---|---|
| 4 | 1774 | 566 | 203 | 111 |
| 8 | 4191 | **1342** | 521 | 260 |
| 16 | 9109 | 2942 | 1027 | 513 |
| 32 | 19633 | 6320 | 1821 | 785 |

主口径导出(T=8, S5_C0.4):**1342 边 / 17 项目**(对比 bug-fix 仅 157 边 → 样本扩约 8.5×)。

### E2 — evo 边静态可见性(import 级,多口径)
- **关键诚实限定**:1342 边里 **709(52.8%)的文件在当前 HEAD 已不存在**(历史上删/改名/重构),
  无法算 HEAD 静态可见性,**记为 absent_at_head、不计入率**。只有 **633 条**两端文件在 HEAD 都在。
  → evo 共改边覆盖了大量已消失的历史文件,这是 mined-over-history 的固有代价,如实标注。

| (n=633) | strict | med | loose |
|---|---|---|---|
| **静态可见率** | 44.6% | 71.6% | 91.9% |
| **静态不可见率** | 55.5% | **28.4%** | 8.1% |

**不可见边子类型(med,共 180 条)**:dynamic_or_registry_hint **119**、same_dir_sibling 37、package_init 22、cross_dir 2。

### Phase E 与 bug-fix(Phase 1-2)对比(纯描述,不下结论)
| | 共改边数 | 不可见率(med) | 不可见里 dynamic 占比 |
|---|---|---|---|
| bug-fix(157) | 157(fetched 144) | 19.4% | 9/28 ≈ 32% |
| evo coupling(1342) | 1342(fetched 633) | **28.4%** | **119/180 ≈ 66%** |

→ 描述:扩样本后不可见率(med)更高、且不可见边里"动态/注册表线索"占主导。
**不下结论**:这可能反映 evo 信号更能捕到动态耦合,**也可能是** keras/youtube-dl 等动态密集项目在 evo 边里占比更大造成的合成效应——需人工分项目核(见待判点)。
**所有 Phase 2 的诚实限定(import 级代理、非 repo_parser、共改≠依赖)同样适用本节。**

---

## Phase E3(承重数字校准):用项目自己的 repo_parser 替换 import 代理

按"任务三前置"要求:之前的盲区率(bug-fix 19.4% / evo 28.4%)是 **import 级简化代理**,
非项目自己的 repo_parser(tree-sitter,抓 **import + 调用 + 继承** 边)。专家诚实标注"可能高估盲区"。
本节用 **repo_parser 原版(从 `D:/claude/49/src` 导入,未改)** 在全 checkout(HEAD,sparse 只检出 .py)上重判。
脚本 `pe3_repoparser_calibration.py`。

**方法**:parse_repo 出仓库的文件级静态邻接 = import_edges ∪ (call_edges 按"函数名→文件"提升) ∪ (class_edges 按"类名→文件"提升)。
共改边 (A,B) 在该邻接里任一方向连通即"静态可见"。三口径:import-only / +call / +call+inherit(权威)。

**结果(全样本,HEAD 在场边;absent_at_head 不计入率)**:

| | n(present/total) | 盲区 import-only | 盲区 +call | 盲区 +call+inherit(**权威**) |
|---|---|---|---|---|
| **bug-fix 边** | 109/157(absent 48) | 54.1% | 23.85% | **23.85%** |
| **evo 边** | 633/1342(absent 709) | 61.0% | 31.75% | **30.65%** |

**与 import 代理对比(同 HEAD、同边集)**:
| | 代理 strict | 代理 med | 代理 loose | repo_parser import | repo_parser **FULL** |
|---|---|---|---|---|---|
| bug-fix 盲区 | 52.1% | 19.4% | 12.5% | 54.1% | **23.85%** |
| evo 盲区 | 55.5% | 28.4% | 8.1% | 61.0% | **30.65%** |

### ⚠⚠ E3b 关键校准:权威盲区数字对"歧义名上限"高度敏感,不是稳定点估计

cap=5 只是陡峭曲线上的一个点。做敏感性扫描(`pe3b_cap_sweep.py`,parse 一次多 cap 分类),
盲区(FULL 口径)随 cap:

| 歧义名上限 cap | bug-fix 盲区 | evo 盲区 |
|---|---|---|
| 1(仅全局唯一函数名算调用边) | 44.0% | 46.9% |
| 3 | 28.4% | 36.5% |
| **5(pe3 用的)** | **23.85%** | **30.65%** |
| 10 | 14.7% | 20.7% |
| ∞(接受所有同名调用边) | **4.6%** | **13.4%** |

**纯描述性观察(修正 + 不下"方向成立/不成立"判断)**:
1. **承重盲区数字不稳定**:它随歧义名上限在 **4.6%–44%(bug-fix)/ 13.4%–47%(evo)** 之间滑动。
   → **必须修正"权威口径没把盲区做小"的说法**:在宽 cap(∞)下,repo_parser 确实把盲区压到 ~5%/13%(代理 med 19%/28% 确有高估);
   在严 cap(1)下盲区高达 44%/47%。**没有单一权威数字,它是一个由消歧激进程度决定的区间。**
2. **两端各有偏**:cap=∞ 把任意同名函数(`__init__`/`run`/`get`/`get`…)连成假"可见"边 → **盲区被人为压低(偏低)**;
   cap=1 只认全局唯一名 → 漏掉经同名方法发生的真调用 → **盲区偏高**。真值在两者之间,但 name-based 调用解析给不出。
3. **根因**:repo_parser 的调用边是"按名字"匹配(其源码自述的已知局限,无类型推断)。
   要得到稳定的承重盲区,需**类型/别名消歧的真调用图**(repo_parser 有 `resolve_symbol` 别名链,但未用于调用边消歧)——
   这是把这个数字做硬的前置技术债,**留给讨论**。
4. **import-only 口径稳定且可信**:repo_parser import-only 盲区(54.1% / 61.0%)≈ 代理 strict(52.1% / 55.5%),
   不受歧义名问题影响——但它只算 import 边,不含调用/继承,是盲区的**上界**。继承边几乎不贡献(bug-fix +0、evo +1.1pp)。

**净校准结论(描述,非判断)**:专家担忧的"代理可能高估盲区"——**部分被证实**:在宽消歧下盲区可低至 ~5%/13%;
但在保守消歧下盲区仍 40%+。**这个承重数字当前是测量敏感的区间(约 5%–45%),不是一个能直接拿去跑 task3 的硬点。**
按任务判定线("15%+ → 盲区真"):**取决于 cap**——这本身就是该在 task3 前解决的(定一个有依据的调用图消歧),留给醒来讨论。

**⚠ 本节自身的诚实限定(承重数字必须带着读)**:
- **歧义名上限**:repo_parser 的调用边是"按函数名"匹配(其源码自述的已知局限),大仓里同名函数极多。
  我对"名字映射到 >5 个文件"的 call/class 边做了跳过(避免一个同名函数就连出大量假"可见"边)。
  跳过量很大(keras 跳 24254 条 call、pandas 22487)。**方向**:跳过歧义名使 +call 可见性**偏保守 → 盲区可能偏高一点点**;
  但若全不跳,会制造大量假可见边 → 盲区被人为压低。两头都有噪声,**这个上限是判断性选择,是本节最该人工复核的点**。
- bug-fix 边原本在 fixed_commit 测,这里在 HEAD 重判(文件改名/移动→absent_at_head,48/157)。**非同一时点**,只作 HEAD 口径参考。
- 仍是"对解析器真值",repo_parser 也是静态分析器;共改边才是开发者信号。本节只校准"共改边里静态(三口径)看不见的比例",**不触及"解析器真值=开发者真值"那层(那是补不了的本质局限)**。

---

## Phase E4(收口:cap-free 稳定承重盲区 + 三类分解)

E3b 暴露盲区随歧义名 cap 在 5%–45% 晃,根因是 repo_parser 调用边"按名字匹配"。
本节用 repo_parser **自己的 `resolve_symbol` 别名链(M3-A 建)** 把每条调用边解析到**确切定义文件**
(调用 `run` → 沿 import/alias 链解析到 `serving.py` 的 `run`,而非连到所有叫 run 的文件),
**消除 cap 依赖**。repo_parser 未改,只调用其已有 resolve 能力。脚本 `pe4_resolve_calls.py`。

**稳定承重盲区(cap-free,精确 import+resolved-call+resolved-inherit)**:
| | n(present) | 稳定盲区(精确) |
|---|---|---|
| bug-fix | 109/157 | **53.2%** |
| evo | 633/1342 | **60.2%** |

**但这 53%/60% 必须三类分解读(任务要求,也是关键)**——盲区不是铁板一块:

| 类 | 含义 | bug-fix | evo |
|---|---|---|---|
| ① 精确静态可见 | import / resolve 到确切文件的调用 / 继承 | 46.8% | 39.8% |
| ② namematch_gap | resolve 绑不上、**但存在同名 def/call 链**(方法分发/再导出/漏 import)→ **理论可静态分析** | 43.1% | 43.8% |
| ③ 无任何静态信号 | 无 import、无 resolved/同名调用、无继承 → **候选真·动态/运行时耦合** | **10.1%** | **16.4%** |
| └ 其中带动态标记 | `__import__`/`getattr`/`register`/`importlib` 等 | 4.6% | 8.2% |

**对任务关键问题的诚实回答**:
- **"文件级消歧后成为稳定值了吗?"** → 是。**cap-free,不再依赖参数**。
- **"落在 5%–45% 区间哪里?"** → 精确盲区落在**高位 53%/60%**(接近 import-only 54%/61%)——
  **证实 cap=∞ 的 4.6% 几乎全是同名碰撞的假可见**;精确调用边大多与 import 边重合(Python 调用即 import),
  只 ~3% 的调用能 resolve 到新的跨文件定义,所以加调用边对盲区影响很小。
- **但真正属于"开发者真值方向价值"的,只有第③类 ~10%(bug-fix)/ ~16%(evo)**:
  它们与两文件间**无任何静态信号**,是 resolve 也够不到的真盲区(候选动态/运行时)。
  其余 53%/60% 盲区里有 **43% 是 namematch_gap(resolve 的局限,非真动态)**——
  一个会做方法接收者类型推断的静态分析器能把其中相当一部分判回"可见"。

**抽查(分类站得住)**:
- ③真动态:ansible `modules/uri.py`↔`plugins/lookup/url.py`、`module_utils/urls.py`↔`doc_fragments/url.py`
  ——ansible 插件系统**运行时装配**,模块与其 doc_fragment/lookup 间无任何静态边,共改纯因"同一特性"。**静态不可能,这是方向价值所在。**
- ②namematch_gap:PySnooper `tracer`↔`utils`、ansible connection `local`↔`ssh`(同名方法分发,resolve 的 import 链法绑不上,但关系真实存在、理论可静态)。
- ①精确可见:PySnooper `tracer`↔`variables`(真 import+调用)。

**⚠ 本节诚实限定**:
- **②是上界、③是真盲区的下界附近**:`resolve_symbol` 只跟 import/alias 链,**不做方法接收者类型推断**,
  所以方法分发(`obj.run()`)一律绑不上→大量真静态关系被归入②。即**真盲区(静态不可能)≈③的 ~10%/16%,
  而非精确口径的 53%/60%**;53%/60% 是"当前 resolve 能力下的不可见",含大块②的工具局限。
- ③里仍混有打包噪声(`setup.py`/`__init__` 与版本相关共改)等"非依赖共改"——**需人工滤一遍③才是干净的真动态盲区**(待判点)。
- 仍是"对解析器(含 resolve)真值";共改才是开发者信号。本节只把"静态看不见的比例"做稳定+分层,**不触及"解析器真值=开发者真值"本质局限**。

**净校准结论(描述,非判断)**:承重盲区现在**稳定可报**:
- 想表述"静态(含精确调用)看不见的开发者共改" → **53%(bug-fix)/ 60%(evo)**,但其中 43pp 是 resolve 工具局限(②)。
- 想表述"任何静态分析都够不到的真·动态/运行时共改"(方向真正的、非平凡价值) → **~10%(bug-fix)/ ~16%(evo)**,其中约半数带动态标记。
**这两个数都稳定、不依赖 cap。哪个该作 task3 的承重数字、~10-16% 的真动态盲区是否足以支撑"开发者真值方向"——留给醒来讨论。**

---

## Task 3(已执行,详见 `TASK3_RESULTS.md`):模型能否靠卡片外信号召回盲区边

已在 A800(Coder-14B/vLLM)跑完:任务=给定种子文件 X 从候选池选开发者共改文件,
三条件(no_card / static_card / +humble)× 三层(visible / invisible_namematch / invisible_dynamic)
× 四套(bug-fix/evo × 去噪/raw),judge-independent。GPU 已释放(0 MiB)。
**头条数(描述,非结论)**:visible 层 static_card>no_card(+0.15~0.25,主线确认);
**evo 大样本 invisible 两层 no_card>static_card(+0.07~0.13,四格一致)**——卡片在静态看不见的共改边上似乎困住模型,
但**是否伪影(候选池-卡片交互)需控制实验**,见 `TASK3_RESULTS.md` §5-6。bug-fix 小样本看不到此效应。
**未下方向成立/新发现判断。**

**〔M51 伪影排除,详见 `M51_RESULTS.md`〕** 对 "no_card>static_card on invisible" 做了两个替代解释的控制实验:
**A 文件名巧合——排除**(召回不随文件名相似度变;异名真 gold 召回 0.48 > 同名诱饵误选 0.24);
**B 候选池伪影——排除**(clean 池=gold∪纯随机下 no_card>static_card 不仅存活、反而略增 +0.11/+0.12)。
**两个伪影都扛住了**(不同于 M41/47 被证伪)——谨慎定位为"扛过伪影检验、值得正式研究的**候选**发现":
静态看不见的变更耦合上,模型有卡片外召回能力且静态卡片压制它(呼应 M29 负杠杆)。
**残留限定**:机制未解释、仅 evo/单模型、falsefriends 因客户端连接错误仅 104 干净实例需重跑。**仍未定为"确证新发现"。**

**〔M52 三残留清完,详见 `M52_RESULTS.md`〕** ① **机制**:等长 filler 不压低、random(错误列表)不压低、**只有正确静态卡片压低**(McNemar p<1e-5)→ 排除上下文挤占等平凡解释,是**内容特异锚定**;② **跨模型**:invisible 层 no_card>static_card 跨 Coder/Qwen/internlm(2 家族)方向一致 → 非个体特性;③ **falsefriends 补满 414**(0 错误):异名真 gold 召回 0.47 > 同名诱饵误选 0.28 → 文件名巧合排除在完整样本成立。
**结论:候选发现 → 效应确证(经 5 道对抗检验存活、跨模型显著)**:静态依赖卡片在静态不可见的变更耦合上是**内容特异的负杠杆**(呼应 M29)。**带界**:是 co-change/选择式召回非"理解依赖";机制行为层确证、非注意力层证明;范围 BugsInPy/evo。**不夸大成对甲方强主张。**

**〔第十轮裁定 + M54,详见 `M54_RESULTS.md`〕** 评委从零复现命门 + 自设第六道攻击(预算重分配,被数据反驳)→ **升「优秀(下限),已达到」**,唯一脆弱点 co-change≈依赖(限制"重要性")。M54 攻它(纯 CPU 重切):① 被压低的边 **97% 核心源码耦合、3% 噪声** → 驳"全是 CHANGELOG 噪声";② 负杠杆在 evo 去噪 core_both 存活(p=9.5e-6)、noise 子集消失;③ **但 bug-fix(最强真任务耦合)Δ=0** → evo 高频耦合特异、需基线召回存在,**未跨"co-change=真依赖"**。净:挡下"全是噪声"那刀,加了 evo 特异边界,**未打穿重要性/magnitude 天花板,维持优秀(下限)**。

---

## 需醒来后人工判断的点(不在本文下结论)

1. **static_invisible 的 28 条边里,多少是"真任务耦合"vs"路径映射产物/示例-doc 共改/噪声"?**
   需逐条人工读(尤其 14 条 cross_dir 里有多少是 examples/tutorials 而非真代码耦合)。
2. **med ~19% / strict ~52% 哪个口径更该作头条?** 取决于"包前缀算不算可见"——需定口径再谈幅度。
3. **是否值得用 repo_parser 在全仓重跑**得到权威静态可见性(把代理换成项目自己的静态分析)?
   这会改变不可见率(预期下降,因补上调用/继承边)。
4. **是否扩样本**:157 边偏小;是否引入全 git 历史的 evolutionary coupling(共提交关联规则)
   把共改边规模做大,再做 task3。
5. keras 三后端、ansible galaxy 这类 dynamic_or_registry 边是否就是论点要找的
   "开发者相关、静态看不见的真耦合"——若是,task3 在这子集上的召回才是核心问题。
6. **(evo)evo 不可见率 28% > bug-fix 19%、且 dynamic 占 66%:是 evo 信号本身更能捕动态耦合,
   还是 keras/youtube-dl 等动态密集项目在 evo 边里占比大造成的合成效应?** 需按项目分解核。
7. **(evo)709/1342 边的文件在 HEAD 已消失**:是否改为"在各 bug/各历史时点的快照"上算静态可见性
   (而非统一 HEAD),把这 53% 捞回来?这会改变可见率与样本量。
8. task3 该用哪个共改口径作 gold:bug-fix(157,真实任务耦合、最干净)还是 evo(1342,大但更噪)?
   还是两者都做、对比?
9. **(E4 已收口)cap 依赖已消除**:用 resolve_symbol 得到稳定数字——精确盲区 53%/60%,
   其中真·无静态信号(③)仅 ~10%/16%。承重数字现在稳定可报,不再 5-45% 晃。
10. **(E4 待人工)③类去噪**:③(~10%/16%)里混有 setup.py/__init__ 等打包噪声共改。
    需人工(或规则)把"非依赖共改"滤掉,得到干净的"真动态/运行时耦合"率——这才是方向价值的最终承重数。
11. **(E4 待人工)②namematch_gap(43%)的归属**:它是 resolve_symbol 不做方法类型推断的工具局限,
    不是真动态。要把 53%/60% 收得更紧,需更强静态分析(方法接收者类型推断)把②的可静态部分判回可见。
    **决策**:task3 承重数字用哪个——53%/60%(当前 resolve 口径不可见)还是 ~10%/16%(真静态不可能)?
12. **(task3 决策)** gold 口径(bug-fix 157 干净 vs evo 1342 大);承重盲区口径(②含/不含);
    ③去噪后是否仍有足够样本支撑 task3。**这些定了再启动 GPU。**

**本文只到这里:数字 + 描述 + 限定 + 待判点。结论留给讨论。**
