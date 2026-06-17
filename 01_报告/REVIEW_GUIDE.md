# REVIEW_GUIDE.md — 评委审阅导览(从哪读起 / 结论在哪 / 怎么快速验证)

> 给双评委:这份导览让你**快速定位、快速验证、快速挑刺**。每条核心结论都标了证据文件、验证方式、置信等级。

## 一、5 分钟速览路线
1. **VALUE_FOR_REPOMIND.md** — 一页纸:结论对甲方意味着什么(决策语言)。
2. **INSIGHT.md** ★ — 研究灵魂:核心论断 + 六维度稳健 + 诚实自我修正链 + 独立观点 + 边界总表。
3. 想挑刺可信度 → **REBUTTAL_OR_FIX.md**(外部评委三指控逐条核实+修复)+ **CONFIDENCE.md**(逐结论分级)。

## 二、核心结论 → 证据 → 验证方式 → 置信
| 核心结论 | 证据文件/实验 | 验证方式 | 置信 |
|---|---|---|---|
| 结构化表示是主导杠杆(大效应:严打约4-5×/宽松约2×;〔M56〕非"数量级") | E18/E36/E48,SCALE_STRESS_TEST | 两独立家族裁判 + 用例配对 + 跨语言/工业级 | 🟩 铁(量级词已降级) |
| 跨所测三语言(Go/Java/C)成立(Go/Java/C 非 Python 特性) | E47,CROSS_LANGUAGE.md | 独立裁判,三语言 +0.6~0.93 p<1e-6 | 🟩 铁 |
| 工业级规模保持(CPython,检索未成瓶颈) | E48/E50,SCALE_STRESS_TEST | rerank=80 捕获 97.5%;六格相对结论保持 | 🟩 铁 |
| PE/CoT 在强 RAG 之上无可测增益(已收回) | E44,M17_RESULTS,REBUTTAL | 三独立裁判全 ns(原 +0.02 是 self-judge 伪影) | 🟩 收回坐实 |
| 微调(生成器/检索器/PEFT/DAPT/RL)边际/逼近不超越 | E40-43/E51,RL_RETRIEVER | 独立裁判;RL 检索器 0.958<静态 1.000 | 🟩 穷尽封口 |
| 间接依赖是表示问题:B2 物化即解 | E46,GRAPH_REPRESENTATION | 去循环 gold,0.40→0.99 p=0.001 | 🟩 铁 |
| 完整图 RAG(B3)是过度工程 | E49,GRAPH_REPRESENTATION §6-7 | B3 0.69<B2 0.90 同口径对照 | 🟩 较稳健 |

## 三、可信度护栏(本项目最硬的资产,重点挑刺这里)
- **gen≠judge**:所有结论被评模型≠裁判模型(self-judge 会静默虚高);自查每个分数文件 gen/judge 字段,**0 self-judge 残留**。
- **两独立家族裁判**:Coder-14B(代码专精)+ internLM2.5-7B(非 Qwen 血统),逐题 **两LLM裁判间一致性 κ=0.806(LLM裁判间,非人工IRR)**(回应"单裁判无信度")。
- **用例配对统计**(ttest_rel):不拿重跑次数当样本量(曾犯此错=伪重复,已改正,见 REBUTTAL 指控二)。
- **去循环金标准**:werkzeug由ast独立重抽(100%吻合)+人工;**新工作(跨语言/CPython)M27也补了去循环**(gcc -H/javalang/raw-line+人工,循环贡献仅0~10.5%,E53),接住"新战场循环复发"质疑。
- **外部评委三刀已修复**:self-judge / 伪重复 / 评测循环,逐条磁盘核实→成立→修复(REBUTTAL_OR_FIX.md)。修复后核心结论反而更硬。
- **七次诚实自我修正**(INSIGHT §5):含一次外部触发——研究的可信度不在从不犯错,而在错了能被数据揪出+自己修。

## 四、五样考核交付物定位(对齐 OFFICIAL_REQUIREMENTS)
| 交付物 | 位置 |
|---|---|
| ① 微调权重+Model Card | artifacts/qwen14b-dep-lora/ + MODEL_CARD.md |
| ② PE 方案 | PE_SOLUTION.md + configs/prompts/ |
| ③ RAG 方案+检索质量 | src/repomind_lab/ + EVALUATION_REPORT.md(Recall/MRR) |
| ④ 量化评测报告 | EVALUATION_REPORT.md + EXPERIMENTS.md(E1-E51) |
| ⑤ 可复现实验包 | src/ + scripts/ + data/ + README.md |

## 五、怎么快速验证我们没造假
- 所有评测分数 JSON 在 `results/`(每个含 gen_model/judge_model 字段,可直接核 self-judge)。
- 统计可复算:`scripts/analyze_*.py` 读分数文件即重算 p 值(确定性)。
- 无 GPU 核心链路从零复现:见 README「快速开始」(解析→数据集→检索 baseline→冠军,逐位一致)。
- 甲方场景旁证:**腾讯开源 rapidjson** 上结构化表示同样碾压(E52,诚实标注开源≠私有)。

> 一句话:这是一个**有观点、有边界、经得起复核**的研究。欢迎挑刺——我们已经先把自己挑过一遍(还被外部评委挑出三刀,都修了)。

---

## 六、〔M50-54 扩展〕开发者真值发现:给全新评委的独立复现路径

**一句话(带界)**:用 git **co-change**(开发者行为真值,**真正独立于静态解析器**)发现——
静态看不见的变更耦合上,**正确的静态依赖卡片反而压低模型召回**(内容特异负杠杆);
小而极稳(+0.05~0.11,跨 3 模型 p<1e-5),**co-change≠依赖、行为层非注意力层、evo 特异(bug-fix 上 Δ=0)**。

**这是第十轮真外部评委从零复现(用他自己的代码,逐位吻合)+ 自设第六道攻击被数据反驳后,据以把项目升「优秀(下限),已达到」的发现。**

**怎么独立验证(无需 GPU,5 分钟)**:
```
cd 06_开发者真值发现/
python verify_finding.py      # 从归档逐实例预测+gold 重算全部数字(核心效应/机制/跨模型/falsefriends/文件名)
```
| 要验的检验 | 数据 | 预期 |
|---|---|---|
| ★命门:机制(filler/random vs 真卡片) | data/scores/scores_mech.json | no_card 0.327/filler 0.341/random 0.361/static 0.236;McNemar p=2.1e-5 |
| 候选池伪影 | scores_ctrl_clean.json | clean 池下 no_card−static +0.111(效应非池伪影) |
| 跨模型 | scores_xmodel_{qwen,internlm}.json | 三模型 invisible 层同向 no_card>static |
| 文件名巧合 | scores_ctrl_falsefriends.json | 异名真召回 0.47 > 同名诱饵误选 0.28 |
| 〔M54〕去噪重要性 | pe12/pe13 | 被压低边 97% 核心耦合;evo core_both p=9.5e-6;**bug-fix Δ=0(诚实边界)** |

**置信**:🟩 效应真(评委从零复现 + 5 道对抗检验 + 第六道攻击被反驳);🟨 重要性部分坐实(压的是核心耦合非噪声)但有界(evo 特异、co-change 代理、效应小)。
**完整指南**:`06_开发者真值发现/DEVTRUTH_FINDING_REPRODUCE.md`(诚实限定+残留置顶,机制实验标"命门")。
**诚实链(项目最强资产)**:`HONEST_TRAJECTORY.md`——十次自我修正(含两个亲手撤掉的漂亮发现)+ 真评委裁决轨迹(及格→优秀下限,含优秀回落与重新达到)+ M54 双面结果。
