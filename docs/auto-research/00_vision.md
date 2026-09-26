# 00 · Vision：自动理论科研系统

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 1–4、17、20 节

---

## 1. 一句话定位

**面向控制理论（Koopman / 非线性控制 / 数据驱动控制）的、自带证伪机制与研究记忆的自动科研闭环。**

它不是一个"自动写论文"的 Agent，而是一个能在较长时间尺度上自主推进理论研究的系统：从文献与假设出发，经由创新算子生成 idea、构造理论、对抗式验证、claim-driven 仿真，最终只把**经过对抗仍存活**的结论交给写作。

---

## 2. 目标质量向量

系统产出的每个主张（claim）都应尽可能满足：

```
Novel + Correct + Nontrivial + Supported + Reproducible
```

这五个分量不是形容词，而是可挂证据的检查维度（见 `07_evidence_and_provenance.md`）：

| 分量 | 对应证据类型 | 归属阶段 |
|---|---|---|
| Novel | 文献检索 + prior-art 对抗 | 04 / 07 |
| Correct | 证明 + 反例搜索 + 符号/数值校验（+ 可选形式化） | 05 |
| Nontrivial | 意义检查（Bring 收益 vs 复杂度成本） | 04 / 05 |
| Supported | claim-driven 仿真与 baseline 对比 | 06 |
| Reproducible | 固定种子、配置、代码与数据产物 | 06 / 07 |

---

## 3. 差异化：与现有自动科研系统相比

任务书第 16–17 节已调研 AI-Scientist-v2、Agent Laboratory、AI Co-Scientist、Robin/PaperQA2、autoresearch、Scholar Loop、LeanDojo/DeepSeek-Prover、PaperBench/ScienceAgentBench 等。归纳其主线是：

```
Idea → Code → Experiment → Metric
```

本系统的主线改为：

```
Idea → Mathematical Structure → Theorem → Proof → Falsification → Simulation → Evidence
```

由此产生四条差异化能力，也是本设计的核心资产：

1. **Theorem-first 闭环**：以数学结构而非实验指标为中心，实验只服务于 claim。
2. **对抗式数学验证**：Proof Critic / Counterexample Hunter / 符号-数值 Checker 作为独立关卡。
3. **创新算子库 + Research Pattern Cards**：把"灵感"沉淀成可复用资产，而不是一次性 prompt。
4. **失败记忆（Idea Graveyard）**：长期看比成功论文集合更有价值，且会反向约束 idea 生成。

---

## 4. 输入谱系

用户可以给系统不同强度的起点（任务书第 1 节）：

- 已有部分进展的 idea；
- 一篇或若干篇论文；
- 一个大方向（如 "Koopman control"）；
- 一个研究约束（如"偏理论、只做仿真"）；
- 仅一个领域。

输入强度影响的是 **Problem Framer 的填充量**与 **Literature Scout 的搜索宽度**，不改变下游契约。

---

## 5. 非目标

- **不是**博文/综述生成器；不带 claim 的文本没有价值。
- **不是**纯经验型 AutoML；不以刷 benchmark 为目标。
- **MVP-0 阶段不是**端到端论文生成器。
- **不是**"万能科学家"；初始只在**一个小而结构明确**的研究空间（Koopman/控制）内跑通闭环。

---

## 6. 分阶段路线（来自任务书第 14 节）

| 阶段 | 名称 | 目标 | 主状态机 |
|---|---|---|---|
| **MVP-0** | Research Idea Engine | 输入主题/论文 → 产出有文献支撑、经初步证伪的 2–3 条研究分支 | `08_mvp0_specification.md` |
| **MVP-1** | Theory Research Loop | 自动形成 definitions/assumptions/lemmas/theorems/proofs 并多轮攻击 | `05_theory_engine.md` |
| **MVP-2** | Simulation Research Loop | claim → 实验 → 执行 → 分析 → PROCEED/REFINE/PIVOT/KILL | `06_experiment_engine.md` |
| **MVP-3** | Paper Compiler | 只消费已验证材料，编译稿件并接受对抗 review | `07`（Writer 门禁） |

**本规格集只详细规格化 MVP-0（`08`），并为 MVP-1/2/3 给出足够清晰的下游契约。**

---

## 7. 成功度量（供后续 benchmark 设计）

任务书第 16.11/16.12 节指出：自动科研的质量必须拆成**可独立评分的子能力**。本系统拟以如下分项度量（MVP-0 先覆盖前四项）：

| 分项 | 定义 | MVP-0 目标 |
|---|---|---|
| Literature accuracy | 引用/元数据/结论是否忠实原文 | 可抽检通过 |
| Assumption extraction | 是否正确抽出论文的强假设与限制 | 对给定论文可复现抽取 |
| Gap mining precision | 挖出的 gap 是否真实、非伪 gap | 人工抽检 ≥ 阈值（OQ-07） |
| Novelty detection | 是否误判"没人做过" | 必须带不确定性标签 |
| Proof correctness | 证明是否正确 | MVP-1 |
| Counterexample recall | 能否找到应存在的反例 | MVP-1 |
| Simulation reproducibility | 结果可否复现 | MVP-2 |
| Claim grounding | 每条 claim 是否可回溯证据 | MVP-0 起贯穿 |

> 具体阈值与基准集构成属于开放问题 `OQ-07`。

---

## 8. 设计原则（贯穿）

见 `README.md` 第 6 节。此处强调两条最容易被实现妥协的：

- **对抗优先于一致**：不允许所有 Agent 共享"证明项目是对的"这一目标函数。
- **确定性优先于生成**：能判定就判定，不能判定才生成；生成结果必须被判定。

---

## 9. 与 vibe 工作流的定位关系

本系统是 vibe 工作流的一个**应用层**：vibe 提供状态、证据、复核、编排与门禁；本系统提供科研领域的实体、算子、流水线与判据。二者通过 `07_evidence_and_provenance.md` 第 7 节定义的状态映射耦合，不产生第二套业务事实源。

---

## 10. 本文件涉及的开放问题

- `OQ-01` 初始垂直领域的收窄程度（Koopman 单点 vs 更宽的控制理论）。
- `OQ-07` MVP-0 的量化验收阈值与基准集。
- `OQ-09` 是否把"人类 copilot 模式"设为 MVP-0 的默认形态（任务书第 16.2 节提到 human copilot 与 autonomous 可共存）。
