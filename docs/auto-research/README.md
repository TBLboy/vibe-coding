# 自动理论科研 Agent（Auto-Research）设计规格集

> **分支**：`opencode-auto-research`（从 `opencode` 播种，见 `docs/OPENCODE-SEED.md` 的播种范式）  
> **状态**：设计规格 v0.1 —— **仅有设计，无实现代码**  
> **上游任务书**：`automated_theory_research_agent_initial_design.md`（v0.1，2026-09-23）  
> **定位**：Theory-first Autonomous Research System，聚焦 Koopman / 非线性控制 / 数据驱动控制的理论型研究。

---

## 1. 本规格集要解决什么

任务书给出了系统的**构想与原则**；本规格集把它落成**可评审、可实现、可机器校验**的设计契约。它不是代码，也不替代任务书，而是把任务书中的名词（Research State、Idea/Theory/Experiment Tree、Innovation Operator、Claim Ledger、Kill Criteria、MVP-0 状态机）定义清楚，使另一个有能力的 Agent 能在不重新猜测业务意图的前提下进入实现。

本规格集**复用 vibe 工作流作为引擎**（见第 4 节），不另起一套并行的状态/证据/复核系统。

---

## 1.1 输入溯源（traceability）

本规格集的上游是外部输入的**任务书**：`automated_theory_research_agent_initial_design.md`（v0.1，2026-09-23）。该文件**不在本仓库内**，位于用户工作目录（微信接收目录）：

```text
C:\Users\12187\Documents\xwechat_files\wxid_mbu6ww074nnr12_6edd\msg\file\2026-09\automated_theory_research_agent_initial_design.md
```

因此正文所有"任务书第 X 节"的引用**无法由仓库内独立校验**——这是一个已记录的 **traceability gap（未解决）**。处理选项：(a) 把任务书原文 vendor 进 `docs/auto-research/reference/`；(b) 由用户确认一个稳定可访问的路径。在关闭该 gap 前，本规格集只能保证**内部一致性**，不能保证对任务书的忠实度。

---

## 2. 文档地图

| 文档 | 主题 | 回答的问题 |
|---|---|---|
| [`00_vision.md`](00_vision.md) | 定位与成功度量 | 做什么、不做什么、凭什么区别于现有系统 |
| [`01_research_state_schema.md`](01_research_state_schema.md) | Research State Schema | 系统的事实源是什么、实体/字段/关系/provenance、如何校验 |
| [`02_agent_contracts.md`](02_agent_contracts.md) | Agent Contracts | 每个角色的输入/输出/权限/失败语义/对抗对手 |
| [`03_innovation_operator_library.md`](03_innovation_operator_library.md) | Innovation Operator Library | 如何把"灵感"变成可复用算子与 pattern card |
| [`04_idea_search_and_kill_criteria.md`](04_idea_search_and_kill_criteria.md) | Idea Search & Kill Criteria | 多分支 idea 如何生成、筛选、淘汰、复活 |
| [`05_theory_engine.md`](05_theory_engine.md) | Theory Engine | 定义-假设-定理-证明-反例的对抗式流水线 |
| [`06_experiment_engine.md`](06_experiment_engine.md) | Experiment Engine | claim-driven 实验设计、funnel 与确定性裁决 |
| [`07_evidence_and_provenance.md`](07_evidence_and_provenance.md) | Evidence & Provenance | Claim Ledger、证据状态、失败记忆、Writer 门禁 |
| [`08_mvp0_specification.md`](08_mvp0_specification.md) | MVP-0 Specification | 第一个可交付闭环：状态机、事件、产物、验收 |
| [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) | 开放问题总表 | 所有 C 级未决项及其推荐答案与影响 |

建议阅读顺序：`00 → 01 → 07 → 02 → 03 → 04 → 05 → 06 → 08`。  
（先看事实源与证据模型，再看角色与流程，最后看 MVP 落地。）

---

## 3. 术语契约

术语以 `docs/TERMINOLOGY.md` 为全局约束。本规格集新增的领域术语如下，**同一概念只允许一种写法**：

| 术语 | 含义 |
|---|---|
| **Research State** | 整个研究项目的结构化事实源（见 `01`）。不是聊天记录。 |
| **Idea / Theory / Experiment Tree** | 三条独立但可互相引用的演化树；Idea 是方向，Theory 是其数学实现，Experiment 是其经验检验。 |
| **Innovation Operator** | 形如 `O:(Problem, Gap, Assumption) → CandidateIdea` 的可复用创新推理算子。 |
| **Research Pattern Card** | 从真实论文沉淀出的"创新推理模式"卡片，是 Operator Library 的经验来源。 |
| **Claim Ledger** | 项目级主张账本：每条 claim 的证据、验证方式与状态。 |
| **Failure Memory / Idea Graveyard** | 一等公民的失败记录，含最小反例与 salvage paths；新 idea 生成前必须先检索。 |
| **provenance** | 任何对象都必须携带的来源信息：谁生成、基于什么、哪次 run、是否验证过、被谁引用。 |
| **Kill Criteria** | 独立于"想继续做"的、可执行的淘汰判据。 |
| **GO / NO-GO** | 独立复核结论，语义与 vibe 工作流的 review verdict 一致。 |

---

## 4. 与 vibe 工作流的关系（复用边界）

本系统**不自建**持久化状态、证据账本、复核与任务编排，而是复用当前仓库（`opencode` 分支）已验证的机制：

| 本系统概念 | 复用的 vibe 概念 | 说明 |
|---|---|---|
| Research State 的持久化与派生视图 | `.project-log` 状态库（Project Log format 2，SQLite store schema 3）+ 生成视图 | 结构化事实进状态库，长正文进 `.project-log/docs/**` |
| Claim Ledger 的证据状态 | evidence 状态机 `candidate/valid/failed/stale/superseded/invalid` | 沿用同一套语义与失效规则，不新造状态名 |
| 对抗式复核（Theory Critic / Adversarial Review） | `verification-reviewer` / `alignment-reviewer` 独立复核 + `go/no-go/conditional` | 复核者不得复用实现者结论 |
| 研究分支推进与切换 | task/run 生命周期 + loop decision（`PROCEED/REFINE/PIVOT/KILL`） | KILL 对应 `task.cancel` 的语义 |
| Agent 角色与权限 | OpenCode subagent + 只读/写入范围边界 | 见 `02_agent_contracts.md` 的权限矩阵 |
| 失败归因 | 既有失败来源分类（implementation / specification / environment / …） | 归因类别沿用，不自造 |
| 预算与证据门禁 | `vibe gate` / required evidence | 声明完成前必须过门禁 |

**边界**：本规格集描述的是"应用层"。它**不修改** vibe 工作流既有运行时代码；若发现必须扩展引擎能力，应作为独立任务在 `opencode`/`main` 线上评估，而不是在本分支私自改动。

---

## 5. 本规格集不覆盖的内容（明确非目标）

- 具体 LLM / 框架 / 数据库的最终技术选型（候选见任务书第 15 节，属 `solution-research`）。
- 论文 LaTeX 模板与投稿排版（属 MVP-3）。
- 形式化验证（Lean）的工程接入细节（属 MVP-1 可选层）。
- 任何应用层实现代码、脚手架或可运行骨架（本分支只交付设计）。
- 修改 vibe 工作流现有 Agent / Skill / runtime。

---

## 6. 约束与原则（贯穿全部文档）

1. **Theory-first**：以数学结构与可证伪性为中心，不以"跑出好看曲线"为中心。
2. **证据先于结论**：没有可追溯证据的结论一律不得进入论文材料。
3. **失败是一等公民**：失败研究必须归档，且会影响后续 idea 生成。
4. **对抗设计**：至少有一条角色链以"证伪/推翻"为唯一目标。
5. **确定性优先**：凡是能交给确定性工具（SymPy/NumPy/CVXPY/求解器）裁决的部分，不得只依赖 LLM 判断。
6. **Writer 不创造事实**：写作阶段只能消费已验证 claim。
7. **有限循环**：任何重试/重跑必须给出可证伪假设、相对上次的差异与预期证据变化（与 vibe Loop Control 一致）。

---

## 7. 开放问题

所有未决的 C 级语义选择统一登记在 [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md)，并在各文档正文以 `OQ-xx` 引用。这些问题**不阻塞设计评审**，但阻塞对应阶段的实现：实现前必须由用户批准。

---

## 8. 状态与下一步

- 当前：设计规格已落稿，等待独立复核（GO/NO-GO）。
- 下一步：用户在开放问题上给出选择后，进入 MVP-0 的 `solution-research` 与技术选型，再进入实现。
