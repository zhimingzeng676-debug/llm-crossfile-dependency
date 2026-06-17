# 开发者真值发现 — 评委从零复现指南

> ⚠⚠ **M56 机制大幅下修(必读,改写下文"内容特异"措辞)**:补干净对照 `random_in_pool`(随机文件强制入池,入池率与 static 可比)后证实——
> "负杠杆"在 invisible 层**主要是固定输出选择任务里的机械挤占**(任何入池候选列表都挤占未列项召回),**非"内容特异锚定"**:
> random_in_pool 压低 invisible 召回与正确静态卡片**一样多**(0.282≈0.285,**McNemar p=0.94**)。M52 的"内容特异"是 random_card 出池(入池率 0.09)的混淆产物。
> **下文凡"内容特异负杠杆"按此降级读;机制定论见 `M56_RESULTS.md`。** 仍真实:co-change 静态看不见的边 + 模型凭语义召回约 1/3 + 给卡片后召回降;被推翻:降低是内容特异。
> 另:全文 **"judge-independent" 主线义为 "LLM-judge-independent(parser-anchored)"**;但 **co-change 发现的 gold 本身是非解析器的**(分层用 repo_parser,gold 用 git 共改)——这是它顶破 parser-truth 死结的点。
>
> ⚠⚠ **M57 再下修(必读)**:本文"模型召回约 1/3 静态看不见边 = 卡片外能力"经**开放生成**(绕开挤占)+ 信号分解证实:召回真实,**但 ~94% 是平凡信号**(text_clue 63% 读到代码里已有的名字 + 文件名 10% + 包结构启发 21%),**真语义直觉补盲残差 ≤1.8% 且像项目记忆**。**"模型能语义补盲"这条线诚实关掉。** co-change 方向净贡献 = 正交真值验证主线 + 量化盲区(10-16%)+ 两次诚实证伪(负杠杆=挤占、补盲=平凡信号)。详见 `M57_RESULTS.md`(verify 用 `scores_opengen_nocard.json` + `pe17/pe18`)。

> 本目录(`06_开发者真值发现/`)归档 M50-52 的一个发现及其**五道对抗检验 + 跨模型**的完整证据链。
> 设计目标:评委用归档的**原始逐实例数据 + 脚本 + gold**即可独立复现每一道检验,**无需重跑 GPU**
> (提供纯 CPU 校验脚本 `verify_finding.py`,从逐实例预测重算所有数字)。

---

## 0. 诚实限定(置顶,先读)

这个发现**确证的是一个效应**,不是一个大主张。措辞必须带界:
1. **co-change ≠ 依赖**:gold 是 git 共改(开发者修一个真实 bug / 历史共提交时实际一起改的文件),
   是**开发者行为信号**,不是"开发者主观认定的依赖"。全文称"变更耦合",不写"模型理解依赖"。
2. **行为层确证,非注意力层证明**:机制("正确静态卡片把模型锚定到静态邻居")由对照实验(filler/random)
   在**行为层**坐实,**未做**注意力权重/探针级证明。
3. **选择式召回**:任务是"从候选池选共改文件"(gold 恒在池中,recall 上限 1.0),非开放生成。
   已用 clean 池证明效应非候选池伪影,但仍是选择式。
4. **范围**:BugsInPy 17 项目、evo 共改为主(bug-fix 小样本欠功效);单 temperature=0;humble 仅弱救回。
5. 静态可见性分层(visible/invisible)由**解析器(repo_parser + resolve_symbol)**定义,非开发者主观。
   "静态不可见层"按构造不在 static_card 里——所以 static_card 在该层召回低含**定义性成分,不是头条**;
   头条是 **no_card 在该层非零召回 + no_card>static_card 方向跨模型显著**。

## 0b. 已知残留(未做/补不了,如实列)
- 注意力层机制实验(未做)。- 开放生成式任务复现(未做)。- 更多模型家族 / 温度敏感性(未做)。
- **对"开发者主观真值"(非 co-change、非解析器)的验证——本质局限,当前条件补不了。**

---

## 1. 一句话发现(带界)

> 在**静态分析(import + resolve_symbol 精确调用 + 继承)看不见**的开发者**变更耦合**边上,
> LLM 靠卡片外信号(读种子代码语义/结构,**非文件名**)召回约 1/3~1/2;
> **提供正确的静态依赖卡片会显著、内容特异地压低这个召回**(no_card−static_card 在 invisible 层 +0.05~0.10,
> McNemar p<1e-5,跨 Coder-14B/Qwen-14B/internlm-7b 三模型一致),同时抬高静态可见边召回。
> 即**静态依赖卡片在静态看不见的耦合上是"内容特异的负杠杆"**——把模型锚定到静态邻居。呼应主线 M29。

---

## 2. 无 GPU 一键校验(推荐评委先跑这个)

```
cd 06_开发者真值发现/
python verify_finding.py        # 纯 CPU,从 data/scores + data/instances 重算全部数字
```
它会重算:核心效应(evo_raw/denoised)、机制四条件+McNemar、跨模型三模型、falsefriends 诱饵精度、
文件名 jaccard-召回。**所有数字应与下表一致。**

---

## 3. 五道检验逐项(测什么 / 原始数据 / 复现命令 / 预期数字)

### ★ 检验④ 机制(命门 —— 请重点复现)
**测什么**:"给卡片后 invisible 召回降低"是平凡的上下文挤占,还是正确静态内容的锚定?
四条件:`no_card` / `filler_card`(等长无关填充,无文件路径)/ `random_card`(同格式但随机错误文件)/ `static_card`(真)。
**filler/random 构造可复现**:见 `scripts/pe10_build_mech.py`——
filler = 中性句 `"This section contains general background..."` 重复到 **len(static_card)** 后截断(无文件路径);
random = 解析真卡片每类(imports/imported_by/calls_into/inherits)的**条目数**,用同数量的**随机非 gold 仓库文件**填充(按 `md5(seed+f)` 确定性排序采样)。
**原始数据**:`data/scores/scores_mech.json`(414 实例逐条预测)+ `data/instances/instances_mech.json`(种子/候选/卡片/filler/random/gold+分层)。
**复现命令**:`python scripts/pe11_mech_sig.py`(读 mech 数据,出四条件召回 + McNemar)。
**预期数字**(invisible_dynamic / namematch / visible 召回):
| 条件 | dynamic | namematch | visible |
|---|---|---|---|
| no_card | 0.327 | 0.379 | 0.665 |
| filler_card | 0.341 | 0.376 | 0.654 |
| random_card | 0.361 | 0.410 | 0.670 |
| static_card | **0.236** | **0.312** | **0.734** |

McNemar(invisible 全样本 n=762):static_card vs no_card **p=2.1e-5**;vs filler **p=6.3e-6**;vs random **p=1.3e-11**。
**判读**:filler≈no_card→非上下文挤占;random≈no_card→非"有列表即锚定";只有真卡片压低→**内容特异锚定**。

### 检验① 文件名巧合
**测什么**:no_card 的 invisible 召回是否只是文件名相似匹配?
**数据/命令**:① 全样本 jaccard-召回:`python scripts/pe7_filename_analysis.py`(读 evo_raw)。
② 假朋友精度:`data/scores/scores_ctrl_falsefriends.json`(满 414)+ `python scripts/pe9_ff_analysis.py`。
**预期**:召回**不随文件名相似度变**(jacc==0 召回 0.321 ≈ jacc≥0.5 召回 0.333);
异名真 gold 召回 **0.467** > 同名诱饵误选 **0.277** → 非文件名驱动。

### 检验② 候选池伪影
**测什么**:no_card>static_card 是否候选池构造与卡片的交互假象?
**数据**:`scores_ctrl_orig.json` / `scores_ctrl_clean.json`(clean=gold∪纯随机,无静态邻居/无同名干扰)+ `instances_ctrl_*.json`。
**构造脚本**:`scripts/pe8_build_control_pools.py`。**复现**:`verify_finding.py` 内含,或直接读两文件 summary。
**预期**:clean 池下 no_card−static_card invisible_dynamic **+0.111**、namematch **+0.117**(效应存活反增)→ 非池伪影。

### 检验⑤ 跨模型
**数据**:`scores_mech.json`(Coder)/ `scores_xmodel_qwen.json` / `scores_xmodel_internlm.json`,同 `instances_mech.json`。
**预期**(invisible_dynamic no_card vs static_card):Coder 0.341/0.245、Qwen 0.356/0.293、internlm 0.490/0.404——**三模型同向**。

### 核心效应(分层召回)
**数据**:`scores_evo_raw.json`(638,完整)+ `scores_evo_denoised.json`(551)+ `instances_evo_*.json`。
**预期 evo_raw**:visible no_card 0.585/static 0.738;invisible_namematch 0.383/0.309;invisible_dynamic 0.322/0.240。

---

## 4. gold 来源与分层(可复现)
- **co-change gold**:`scripts/p1_extract_cochange.py`(bug-fix:从 BugsInPy `bug_patch.txt` 抽开发者共改源码文件,test 分离,tangling 去噪报两版)、
  `scripts/pe1_evo_coupling.py`(evo:全 git 历史共提交关联规则,support≥5/confidence≥0.4,提交封顶 30000,tangling 阈值扫描)。
  gold 数据:`data/gold/p1_*.json`、`pe1_edges_primary_*.json`。
- **静态可见性分层**:`scripts/pe4_resolve_calls.py`——用项目原版 `repo_parser.resolve_symbol`(未改)把调用边解析到确切文件,
  分 visible(精确 import/调用/继承)/ invisible_namematch(有同名链但 resolve 绑不上)/ invisible_dynamic(无任何静态信号)。
  分层数据:`data/gold/pe4_*_class_*.json`。cap 敏感性见 `pe3b_capsweep_*.json`。
- **实例构造**:`scripts/pe5_build_instances.py`(种子-候选池-卡片-gold)。

## 5. GPU 从零重跑(可选,需 A800 + vLLM)
原始打分由 vLLM 服务模型 + `scripts/task3_score.py`(OpenAI 兼容,localhost)产生;
驱动脚本 `scripts/run_*.sh`(serve→wait_ready→score→nuke 释放显存)。
SSH 驱动模式(paramiko)见交付根 README;**本归档脚本不含任何凭据**。
温度=0,WORKERS=10。重跑应在统计噪声内复现上述数字。

---

## 6. 文件清单(md5 见 `MANIFEST_md5.txt`)
- `verify_finding.py` — 无 GPU 一键校验(命门)
- `scripts/` — p1/pe1/pe4/pe5/pe8/pe10(gold+实例+控制池构造)、pe7/pe9/pe11(检验分析)、task3_score.py、run_*.sh
- `data/gold/` — co-change gold + 静态分层
- `data/instances/` — 8+ 套实例(种子/候选/卡片/filler/random/gold)
- `data/scores/` — 全部逐实例预测(核心效应/机制/跨模型/三控制池)
- `PILOT_RESULTS.md` / `M51_RESULTS.md` / `M52_RESULTS.md` — 完整叙事与判决

**本指南不下"确证能冲优秀"判断;只提供让评委独立验证"效应存活五道检验"的完整路径 + 诚实界与残留。**
