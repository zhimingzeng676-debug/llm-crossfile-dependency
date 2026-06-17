> ✅ **2026-06-15 修复闭环(M17,以 `M17_RESULTS.md` / `E44` 为准)**:已用**三裁判(self对照 + 独立Coder + 独立internLM,
> 两不同家族)**对全部主条件**生成固定重判**,坐实结论:**RAG 主效应**三裁判全 p<1e-10、deep 0.94 头条在独立裁判下成立
> (Coder 0.915 / internLM 0.954)、self-judge 反而**略低估** RAG;**CoT 增益**三裁判全不显著,**正式收回**;
> **System/few-shot** 维持无效。两独立家族 两LLM裁判间一致性 **κ=0.806**(注:LLM裁判间,非人工标注者IRR)(回应"单裁判无信度")。**self-judge 实质只污染了 CoT 一条。**
>
> ✅ **2026-06-15 指控三闭环(M18,以 `DECOUPLED_GOLDSET.md`/`E45` 为准)**:针对"评测同源(testcases/卡片/裁判同出 tree-sitter)",
> 造**与 tree-sitter 完全解耦的金标准**(Python ast 独立重抽,forward/reverse/symbol 与 tree-sitter **100% 吻合**;别名/传递难例人工读源码核验)。
> 去循环 gold 复测:**RAG 主效应仍 +0.66~0.70(p<1e-10)**,与 tree-sitter gold(+0.73~0.77)几乎一致,循环贡献仅 4~15%。
> **→ 评委三条指控全部从"承认"推进到"修复/验证";RAG 主导不是循环伪影。**
>
> ⛔ **2026-06-15 收回声明(以 `REBUTTAL_OR_FIX.md` 为准)**:本文档 §2/§3/§6 的核心判定
> **"32 个主结果文件 = 独立 base 裁判 ✅、全清白"是错的**。外部评委复核 + 重查 `gen_model`/`judge_model`
> 证实:werkzeug/rich 主结果(baseline/full/pe_*/dep_only/sim_only/fuse/deep)的 **gen 与 judge 都是同一个
> base Qwen-14B = self-judge**。本审计的判据写错了——只验"裁判是 base",漏验"被评是否同一个 base"。
> 影响:**RAG 主效应**经独立 Coder 裁判(+0.578)+ 检索指标证实**仍稳健**;**CoT 增益**经独立裁判**翻盘为 −0.024,予以收回**。
> 详见 REBUTTAL_OR_FIX.md。以下原文保留作为"审计自身也有盲区"的证据,不再代表当前结论。

# CONTAMINATION_AUDIT.md — 历史评测污染审计(M15 主动发起)

> **动机**:M15 出现 self-judge + 多实例并发污染(根因:wakeup 重复启动 detached 编排)。
> wakeup 机制 M1-14 一直在用,self-judge 不报错、只让分数虚高,极其隐蔽——必须主动查,
> 用**日志和数据**说话,不下"检查过没问题"的空结论。
>
> **审计方法(可验证)**:每个 `gen_multi` 结果文件都记录了 `gen_model` 与 `judge_model` 两个字段,
> 且每条 run 的 56 个分数可逐一检查。故 self-judge 与并发失败都能从**数据本身**直接审出,不靠回忆。

---

## 1. 并发污染审计(找"多实例抢 GPU"的痕迹)

**签名**:GPU 被多实例抢占时,生成/判分调用失败 → gen_multi 重试耗尽后返回 ERROR → 判分 0 → 整条 run overall≈0。
故"某文件含 overall≈0 的失败 run"= 并发污染的可验证签名。

**数据(扫描全部 35 个 multi/score 文件):**
- **32 个文件:0 个 overall≈0 run** ✅ 干净。
- **3 个文件含 0 值 run**:`multi_ftonly_{dora,ia3,dapt}.json` —— **全部是 M15 这次事故**(eval_all.sh 被 wakeup 重复启动 → 6 实例并发),
  已识别、已隔离为 `*_CONTAMINATED.json` 证据、已用单实例锁重跑。

**结构性论证(为何 M1-14 免疫)**:M1-14 的评测一律通过 `run_remote.py` 跑——它对**单个**配置 serve+gen+download,
**阻塞直到完成**,一次只有一个 vLLM、一个评测。没有 detached 编排可被 wakeup 重复拉起。
唯一的 detached 编排是 M15 的 `eval_all.sh`,污染就唯一出现在它身上。

**裁决:🟢 无任何历史并发污染**(数据签名 + 结构论证双重确认)。

---

## 2. 裁判独立性审计(找 self-judge:被评模型给自己打分)

**数据(逐个文件读 judge_model):**
- **32 个文件:judge = `Qwen/Qwen2.5-14B-Instruct`**(M4 校准过的独立 base 裁判,对人工 MAE 0.022)✅。
- **2 个历史文件 self-judge**:`multi_coder_full_general` / `multi_coder_pe_cot`(M9 第四层跨模型),gen=judge=Coder-14B。
- **3 个 M15 _CONTAMINATED**:gen=judge=merged(已知、已重跑)。

**M9 Coder self-judge 逐项核查**:
- 绝对分 0.76 / 0.79 —— **合理**,非 DoRA 那种 0.40 虚高(self-judge 在此抬升有限)。
- 结论是 **within-model delta**(CoT 增益 = pe_cot − full,两条件都用同一 Coder 自判)= +0.034,p=0.0004。
  **self-judge 抬绝对水平、但不偏两条件之间的 delta**,故跨模型"CoT 增益复现"的结论对 self-judge 稳健。
- M9 **E35 当时已显式披露**"用 Coder 自判,未人工校准"——是**已声明的 caveat,非隐藏污染**。
- 兜底:核心 CoT 结论(E32,general base 独立裁判,n=15,+0.020 p=0.001)**独立成立**;Coder 那次只是第四层"换模型复现"的次级确认。
- **处置**:为给**干净证据**,用独立 base 裁判重验 Coder 跨模型 CoT 增益(见 §5)。

**M8 第二裁判(非 self)**:`judgeanswers_*_cj.json`(6 个)是 Coder 判**他人(general/dep)生成**的答案——
gen≠judge,是**刻意的交叉验证第二裁判**,不是 self-judge。✅

---

## 3. 重点结论复查清单(每条标裁判独立性 + 并发状态)

| 决定性结论 | 证据 | 裁判 | 并发 | 裁决 |
|---|---|---|---|---|
| RAG 是数量级杠杆(+0.5~0.7) | E18/E25/E32/E36 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| CoT 在 RAG 之上小而真(+0.02) | E32(n=15) | 独立 base | 无 0 值 | 🟢 已验证干净 |
| FT 出局(正提升但弱于&冗余于 RAG) | E25/E40 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| 检索深度 rerank 12→80(+0.14) | E37/E38 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| 相似度检索单用 ≪ 依赖检索 | E37 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| 微调检索器 embedding 不是杠杆 | E41 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| few-shot/System-prompt 噪声内 | E32 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| 自评估降幻觉 79%→0.1% | E39 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| 跨项目泛化(rich/pydantic/yaml) | E27/E31 | 独立 base | 无 0 值 | 🟢 已验证干净 |
| **跨模型 CoT 增益复现(Coder)** | E35 | Coder 自判 → **已用独立 base 裁判重验** | 无 0 值 | 🟢 **已验证干净**(base 裁判 +0.063>self +0.034,§5) |
| PEFT 变体 / DAPT(M15) | E42/E43 | 初次 self-judge 污染 | 初次并发 | 🔵 **已发现并重跑**(独立 base + 单实例锁) |

---

## 4. 总裁决

- **并发污染:仅 M15 一次**(eval_all.sh 被 wakeup 重复启动),已修复(单实例锁)。M1-14 数据 0 个失败 run,结构性免疫。
- **self-judge:历史仅 M9 Coder 一处,且已披露 + 为 within-model delta + 绝对分合理**——结论稳健,但仍按最高标准用 base 裁判重验(§5)。
- **其余所有决定性结论:独立校准 base 裁判 + 无并发,已验证干净。**
- **无"日志不足无法确认"的存疑项**——因为每个结果文件都自带 gen/judge 字段与逐 run 分数,审计可完全基于数据。

> 主动审计的意义:本项目最强的是结论可信。self-judge 恰是能从根上摧毁可信度的隐患。
> 这次审出"历史仅一处已披露的 Coder 自判 + M15 一次已修复的事故",并给出数据证据——
> 比默认干净强一百倍。**§5 重验后,Coder 那条若确认 → 全清白;若有偏 → 老实更新。**

## 5. 待办:Coder 跨模型 CoT 增益的独立 base 裁判重验

重跑 `coder_full_general` / `coder_pe_cot`(gen=Coder,**judge=独立 base**,n=15,`eval_coder.sh`),比对 CoT 增益:

| | full(RAG only) | pecot(PE+RAG) | CoT 增益 |
|---|---|---|---|
| 原 self-judge(M9) | 0.757 | 0.790 | **+0.034** |
| **新 独立 base judge** | 0.725 | 0.788 | **+0.063,p<0.0001** |

**结果:方向一致(都为正),且 base 裁判下增益更大(+0.063 > +0.034)。**
→ **self-judge 不但没虚高 CoT 增益,反而略低估了它**(within-model delta 本就对 self-judge 稳健,这里实测确认)。
→ **E35"CoT 增益跨模型(Coder)复现"结论确认干净**,本审计 🟡→🟢。(绝对分在 base 裁判下略降,符合"base 对 Coder 答案略严"的预期,不影响 delta。)

## 6. 最终裁决(审计闭环)

**全部 11 条决定性结论现已 🟢 已验证干净**(原 🟡 Coder 经独立 base 裁判重验通过;🔵 M15 已修复)。
- **并发污染**:仅 M15 一次(已修复,单实例锁);M1-14 数据零失败 run、结构性免疫。
- **裁判独立性**:历史唯一的 Coder 自判经重验确认结论稳健(且 self-judge 在此低估而非虚高)。
- **无任何"日志不足无法确认"的存疑项。**

> 本审计用**数据本身**(每个结果文件自带 gen/judge 字段 + 逐 run 分数)给出可验证的清白证据,
> 而非"检查过没问题"的空结论。主动审出一次事故 + 一处已披露自判,并都给了干净证据——
> 这比假装它没发生强一百倍,也正是本项目"结论可信"的根。
