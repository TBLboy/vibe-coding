# 02 · Agent Contracts

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 4.3、5、8 节  
> 依赖：`01_research_state_schema.md`（实体/ID）、`04`、`05`、`06`、`07`

---

## 1. 目的

把"多 Agent 科研系统"落成**显式契约**：每个角色的输入、输出、权限、失败语义与**对抗对手**必须写清楚，否则系统会退化为"一群 agent 合谋证明项目是对的"（任务书第 4.3 节明确禁止）。

**三条硬规则**：

1. **对抗规则**：每个"建设性"角色必须有一个以推翻它为目标的对手角色。
2. **独立规则**：验证者不得读取被验证对象的内部推理过程，也不得复用其结论（与 vibe `verification-reviewer` 一致）。
3. **权限规则**：角色只能写自己契约声明的对象类型（最小写入范围），跨范围写入必须走 Director。

---

## 2. 角色总表

| # | 角色 | 类别 | 主要产出 | 对抗对手 |
|---|---|---|---|---|
| A1 | Research Director | 编排 | 分支决策（PROCEED/REFINE/PIVOT/KILL）、预算分配 | ——（受 Kill Criteria 约束） |
| A2 | Problem Framer | 框架 | ResearchBrief | —— |
| A3 | Literature Scout | 文献 | Paper、LiteratureCorpus | A4 |
| A4 | Structure Extractor | 文献 | Paper.structured | A3（缺证据的抽取） |
| A5 | Prior-Art Hunter | 对抗 | prior-art 证据、novelty 反驳 | A8 |
| A6 | Gap/Assumption Miner | 挖掘 | Assumption、Gap | A4 |
| A7 | Idea Generator | 创意 | Idea（候选） | A9/A10/A11 |
| A8 | Novelty Advocate | 对抗/支持 | novelty 证据 | A5 |
| A9 | Feasibility Checker | 对抗 | feasibility verdict | A7 |
| A10 | Significance Checker | 对抗 | significance verdict | A7/A8 |
| A11 | Falsification Screener | 对抗 | 初步反例/证伪 | A7 |
| A12 | Theory Builder | 建设 | TheoryNode + Proof | A13/A14/A15/A16 |
| A13 | Assumption Auditor | 对抗 | 假设缺口报告 | A12 |
| A14 | Proof Critic | 对抗（独立） | proof 缺陷报告 | A12 |
| A15 | Counterexample Hunter | 对抗 | 最小反例 | A12 |
| A16 | Symbolic/Numeric Checker | 确定性 | 符号/数值校验证据 | A12 |
| A17 | Formal Verifier（可选） | 确定性 | 形式化证明 | A12 |
| A18 | Experiment Builder | 建设 | Experiment + 代码 | A19 |
| A19 | Adversarial Experimenter | 对抗 | 失效场景实验 | A18 |
| A20 | Run Executor | 确定性 | XRUN + artifacts | —— |
| A21 | Claim Auditor | 仲裁 | Claim 状态与证据绑定 | 全体建设者 |
| A22 | Paper Writer | 组装 | draft（仅消费已验证 claim） | A23 |
| A23 | Adversarial Reviewer | 对抗（独立） | GO/NO-GO + 缺陷 | A22 及全体 |

---

## 3. 角色契约详表

### A1 Research Director（编排）
- **输入**：Research State 全量（只读）、预算、当前分支状态、各角色的 verdict。
- **输出**：分支事件（create/activate/freeze/kill/promote）、资源分配、下一步调度。
- **权限**：可写 `BR-` 状态与 loop decision；**不得**亲自修改 `TH-`/`CLM-`/`EVD-`。
- **失败语义**：无法在预算内产生可用证据 → 记录 blocker 并降级为 `waiting-user`，不得伪造推进。
- **证据义务**：每个 KILL/PIVOT 必须附触发它的证据 id。

### A2 Problem Framer
- **输入**：用户输入（任意强度，见 `00` 第 4 节）。
- **输出**：`RB-`（结构化 ResearchBrief）。缺失字段显式标 `unknown`，不猜测。
- **权限**：只写 `RB-`。
- **失败语义**：输入不足以形成可检验 brief → 产出 `RB-` 且列 `open_questions`，请求用户澄清。
- **证据义务**：`constraints` 中每条必须注明来源（用户陈述 / 推断）。

### A3 Literature Scout / A4 Structure Extractor
- **输入**：`RB-`、检索式、citation graph。
- **输出**：`PAP-` + `structured`（A4）；引用证据。
- **权限**：只写 `PAP-`、`LiteratureCorpus` 与文献类 `EVD-`。**不得**直接产出 Gap 或 Idea。
- **失败语义**：检索不到 → 记录"检索式 + 数据库 + 时间"作为**未命中证据**，不得默认"无人做过"。
- **对抗**：A3 与 A4 互相校验——A4 的每条抽取必须能给回 A3 的原文定位。

### A5 Prior-Art Hunter（对抗）
- **输入**：`IDEA-`、`RB-`。
- **输出**：prior-art 证据 / novelty 反驳。
- **权限**：只写 `EVD-`、`CLM-`（novelty 相关）与 Idea.novelty_evidence 追加。
- **失败语义**：无法证否时必须输出**不确定性标签**（`none_found ≠ none_exists`）。
- **目标**：唯一目标是把"新"证成"旧"。

### A6 Gap/Assumption Miner
- **输入**：`PAP.structured`。
- **输出**：`ASM-`、`GAP-`。
- **权限**：只写 `ASM-`、`GAP-`。
- **失败语义**：无法区分伪 gap 与真 gap → 标记 `confidence=low`，交 A10 复核。

### A7 Idea Generator（创意）
- **输入**：`GAP-` × `OPR-`、`RPC-`、FailureMemory 检索结果。
- **输出**：`IDEA-`（`status=proposed`），必须记录 `origin.innovation_operator` 与 failure_memory_check。
- **权限**：只写 `IDEA-`（proposed）。
- **失败语义**：生成前**必须**检索 FailureMemory；命中则要么附 `salvages` 引用，要么说明与其差异，否则该 idea 被自动拒绝。

### A8–A11 检查类（对抗）
- **A8 Novelty Advocate**：为 idea 找"确实新"的正面证据（与 A5 对抗）。
- **A9 Feasibility Checker**：找数学矛盾、不可满足假设、不可证明风险。
- **A10 Significance Checker**：判断"即便成立是否值得"（generality/收益 vs 复杂度成本）。
- **A11 Falsification Screener**：尝试低维反例/极端参数毁灭 claim。
- **共同契约**：输入 `IDEA-`；输出 `checks.{...}` 的 verdict + 证据；权限只写 Idea.checks 与 `EVD-`；失败语义为 `uncertain` + 不确定性来源（不允许多数投票掩盖不确定）。

### A12 Theory Builder（建设）
- **输入**：`IDEA-`、`ASM-`、`GAP-`。
- **输出**：`TH-`（definition/assumption/lemma/theorem/corollary）+ proof（doc_ref）。
- **权限**：只写 `TH-` 与 proof 文档。
- **失败语义**：证明失败 → 注明缺口（gap in proof），**不得**把未证结论标为 theorem。

### A13 Assumption Auditor
- **输入**：`TH.statement` + `TH.assumptions` + domain 定义。
- **输出**：缺失/多余假设报告。
- **权限**：只写 `EVD-` 与 `TH.assumptions` 追加（标记来源）。
- **失败语义**：无法判断某条件是否必需 → 标记 `unresolved`，不得默认删除。

### A14 Proof Critic（独立）
- **输入**：**只允许** Definitions / Assumptions / Theorem / Proof（**不读 Builder 的推理过程**）。
- **输出**：缺陷报告（缺口/跳步/循环/越界）。
- **权限**：只写 `EVD-`（critique）与 `TH.proof_status` 的 `challenged` 建议。
- **失败语义**：无法定位缺陷 ≠ 通过；输出 `no_defect_found` + 覆盖范围说明。

### A15 Counterexample Hunter
- **输入**：`TH.statement` + assumptions（**允许**读证明，用于定向找反例）。
- **输出**：最小反例（优先 `n=1,2`、退化/奇异/边界、`f(x)=x², sin x, xu`）。
- **权限**：只写 `EVD-`（counterexample）与 `TH.counterexamples`。
- **失败语义**：未找到反例时记录搜索空间（维度、参数网格、随机预算），不得等价于"已证明正确"。

### A16 Symbolic/Numeric Checker（确定性）
- **输入**：可判定的子问题（等式、不等式、数值实例）。
- **输出**：SymPy/NumPy/SciPy/CVXPY 的确定性结果。
- **权限**：只写 `EVD-`（symbolic/numeric）。
- **失败语义**：工具报错/超时 → 记 `failed` + 环境说明；不得用 LLM 结果冒充。

### A17 Formal Verifier（可选，MVP-1+）
- **输入**：高价值 theorem。
- **输出**：Lean/形式化断言 + 验证结果（`EVD-` formal）。
- **失败语义**：形式化不可行时明确标为"未形式化"，不降低其他证据要求。

### A18 Experiment Builder / A19 Adversarial Experimenter
- **A18 输出**：`EXP-` + 代码（`ART-` code）+ 配置。
- **A19 输出**：专门寻找"方法失效场景"的实验（极端 α、边界参数、分布外、噪声）。
- **权限**：A18 写 `EXP-`/code/`ART-`；A19 只写 `EXP-`（adversarial 标签）与 `EVD-`。
- **共同约束**：实验必须绑定 `claim_refs`（见 `06`）；无 claim 的实验判为无效。

### A20 Run Executor（确定性）
- **输入**：`EXP-`。
- **输出**：`XRUN-`（含 seed/config/code hash/result）+ `ART-`。
- **权限**：只写 `XRUN-`、`ART-`。
- **失败语义**：实现失败 → 归因 `implementation/environment` 并重试（须满足 Loop Control 的 retry contract）。

### A21 Claim Auditor（仲裁）
- **输入**：全部 `CLM-` 及其证据。
- **输出**：Claim 状态迁移（`verified/rejected/unresolved/stale`）。
- **权限**：只写 `CLM-` 与 `EVD-`（audit）。
- **失败语义**：证据不足 → `unresolved`，**绝不**默认升级为 verified。

### A22 Paper Writer
- **输入**：**只读** 已验证素材（Claim Ledger `verified` 项、theorem/proof、figure/table、literature 证据）。
- **输出**：稿件草稿（`ART-` manuscript）。
- **权限**：只写稿件产物；**禁止**创建或修改 claim/evidence/theory。
- **失败语义**：素材不足 → 留空并标注 `[NEEDS-EVIDENCE]`，不得用语言润色掩盖空缺。

### A23 Adversarial Reviewer（独立）
- **输入**：稿件的 claim 与证据映射（**独立复核**，不看 Writer 的推理）。
- **输出**：GO/NO-GO + 缺陷清单。
- **与 vibe 对齐**：verdict 词表复用 `go | no-go | conditional`；高风险任务必须有 go 才能过 gate。

---

## 4. 对抗关系图

```
A7 Idea ──┬──> A9 Feasibility ──┐
          ├──> A10 Significance ┤
          ├──> A11 Falsification┘
          └──> A5 Prior-Art ←──> A8 Novelty Advocate
A12 Theory ──┬──> A13 Assumption Auditor
             ├──> A14 Proof Critic        (独立，不读 Builder 推理)
             ├──> A15 Counterexample Hunter
             ├──> A16 Symbolic/Numeric    (确定性)
             └──> A17 Formal (可选)
A18 Experiment ──> A19 Adversarial Experimenter
A22 Writer ──> A23 Adversarial Reviewer (独立)
```

**以证伪/推翻为唯一目标的角色链**（任务书第 4.3 节要求）：`A5 Prior-Art Hunter`（唯一目标：把"新"证成"旧"）与 `A11 Falsification Screener` / `A15 Counterexample Hunter`（唯一目标：用最小反例推翻 core claim / theorem）。这条链的产出与支持性角色**同权**进入证据账本，任何角色不得以"帮助项目成功"为由弱化其结论。

## 5. 权限矩阵（写权限）

| 角色 \ 对象 | RB | PAP | ASM/GAP | OPR/RPC | IDEA | TH | EXP | XRUN/ART | CLM | EVD | BR/loop | REVIEW |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 Director | | | | | | | | | | | ✔ | |
| A2 Framer | ✔ | | | | | | | | | | | |
| A3/A4 Lit | | ✔ | | | | | | | | ✔ | | |
| A5 Prior-Art | | | | | Δ | | | | Δ | ✔ | | |
| A6 Miner | | | ✔ | | | | | | | | | |
| A7 Idea Gen | | | | | ✔ | | | | | | | |
| A8–A11 Checkers | | | | | Δ | | | | | ✔ | | |
| A12 Theory Builder | | | | | | ✔ | | | | | | |
| A13–A17 Verifiers | | | | | | Δ | | | | ✔ | | |
| A18 Exp Builder | | | | | | | ✔ | Δ(cod) | | | | |
| A19 Adv Exp | | | | | | | Δ | | | ✔ | | |
| A20 Run Exec | | | | | | | | ✔ | | | | |
| A21 Claim Auditor | | | | | | | | | ✔ | ✔ | | |
| A22 Writer | | | | | | | | Δ(ms) | | | | |
| A23 Reviewer | | | | | | | | | | ✔ | | ✔ |

`Δ` = 仅限对**自己拥有的字段**做追加/状态建议，不能整对象覆写。

## 6. 编排、预算与升级

- **预算分档**（任务书第 19.5 节）：cheap literature screen → cheap counterexample → small simulation → full simulation → expensive formal。Director 按此梯度分配，禁止对低质量 idea 直接投入最高成本档。
- **升级路径**：任何角色遇 `conflict` 或 C 级语义分歧 → 停下并生成 `open question`，升级给用户，不得自行裁决产品语义。
- **循环上限**：Director 对每个分支设最大迭代与 token/时间预算（与 vibe 会话 Goal 控制面配合）；达上限必须显式 KILL 或进 `waiting-user`。
- **人类 copilot**：MVP-0 允许在 A7→A11 与 A12→A16 之间插入人工 checkpoint（见 `OQ-09`）。

## 7. 统一失败语义

所有角色报告失败时必须给出：`category`（复用 vibe 失败来源词表）+ `evidence` + `next-hypothesis`（如要重试）+ `delta vs 上次`。禁止"未知原因，再试一次"。

## 8. 与 vibe subagent 的映射

本领域角色在 OpenCode 中的实现载体：
- 只读复核类（A14/A16/A21/A23）→ 复用 `verification-reviewer` / `alignment-reviewer` 模式（只读、独立）。
- 文献/结构类（A3/A4）→ 复用 `paper-reader` 的读取契约。
- 建设类（A12/A18）→ 复用 `implementation-builder` 的"最小一致改动 + 不自证"契约。
- 编排类（A1）→ 由 `vibe-main` 承担，不新建 primary agent。

## 9. 开放问题

- `OQ-05` A14 Proof Critic 的"独立"是否需要进程级隔离（不同模型/不同会话），还是记录级隔离即可。
- `OQ-06` A5/A8 的对抗轮数上限与预算分配比例。
- `OQ-09` 人工 checkpoint 的默认开关。
- `OQ-10` A21 Claim Auditor 是单点角色还是多审仲裁（是否存在被单个模型垄断 Claim 状态的风险）。
