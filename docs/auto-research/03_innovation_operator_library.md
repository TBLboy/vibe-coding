# 03 · Innovation Operator Library

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 6、18 节  
> 依赖：`01`（OPR/RPC 实体）、`04`（idea 生成）、`07`（provenance）

---

## 1. 目的

把"给我 10 个创新点"这种不可靠的生成方式，替换为**可复用的创新算子**：

```
O_i : (Problem, Gap, Assumption) → CandidateIdea
```

算子库是本系统的核心差异化资产之一：它让创新有**结构**、可**审计**（这个 idea 用了哪个算子）、可**积累**（新论文 → 新 pattern card → 新算子）。

---

## 2. 算子契约

```
OPR-xxx
  name*            算子名（唯一）
  family*          算子族（见第 3 节）
  signature*       (inputs) → output，形式化描述
  preconditions[]  适用前提（什么 gap/assumption 形态下可用）
  transform*       核心变换的描述（数学上做了什么）
  expected_effect* 预期带来什么（放宽了哪条假设/补了什么保证）
  references[]     来源论文或 pattern card
  provenance*
```

算子本身**不产生结论**，只产生候选方向。它必须由下游检查（`04`）与理论构造（`05`）检验。

---

## 3. 算子族（families）

| 族 | 意图 | 代表算子 |
|---|---|---|
| F1 假设工程 | 让真实问题满足既有理论的条件 | Structure Manufacturing / Dynamic Extension |
| F2 假设放宽 | 修改理论以接受更弱条件 | Relax Assumption / Approximate Condition |
| F3 坐标/表示变换 | 换表示使结构成立 | Coordinate/Latent/Input Transformation |
| F4 增广 | 引入额外状态/观测/输入自由度 | State Augmentation / Observer Augmentation |
| F5 稳健化 | 从精确模型扩展到不确定/扰动 | Robustification / Stochastic Extension |
| F6 数据化 | 从无限/理想数据到有限样本 | Finite-data / Unknown-model Extension |
| F7 分解与分布式 | 降维、解耦、去中心 | Decomposition / Decentralized Reformulation |
| F8 保证增强 | 补齐稳定性/误差界 | Stability Guarantee / Error-bound Addition |
| F9 形式重写 | 换数学形式以获得可解性 | Dual/Alternative Formulation / Regularization |

---

## 4. 初始算子集（来自任务书第 6 节）

| ID | 算子 | 族 | 一句话 |
|---|---|---|---|
| OPR-001 | Relax Assumption | F2 | 放宽已有理论的强假设 |
| OPR-002 | Structure Manufacturing / Assumption Engineering | F1 | 重构问题使原假设成立（CCK virtual dynamics 属此类） |
| OPR-003 | State Augmentation | F4 | 增广状态以补足结构/可观测性 |
| OPR-004 | Dynamic Extension | F1/F4 | 引入额外动态（prefilter/virtual dynamics）制造所需输入结构 |
| OPR-005 | Input / Coordinate Transformation | F3 | 输入或坐标变换使条件成立 |
| OPR-006 | Observer Augmentation | F4 | 增广观测器 |
| OPR-007 | Latent State Introduction | F3/F4 | 引入潜在状态 |
| OPR-008 | Robustification | F5 | exact → 不确定/扰动 |
| OPR-009 | Stochastic Extension | F5 | 确定性 → 随机 |
| OPR-010 | Local-to-Global / Global-to-Local | F9 | 局部结论与全局结论互转 |
| OPR-011 | Finite-data Extension | F6 | 理想结果 → 有限样本结果 |
| OPR-012 | Approximate Condition | F2 | exact 条件 → 近似条件 + 误差界 |
| OPR-013 | Constraint Incorporation | F2/F9 | 把约束显式纳入 |
| OPR-014 | Distributed / Decentralized Reformulation | F7 | 分布式/去中心 |
| OPR-015 | Unknown-model Extension | F6 | 已知模型 → 未知模型 |
| OPR-016 | Dual / Alternative Formulation | F9 | 对偶/替代形式 |
| OPR-017 | Decomposition | F7 | 分块/解耦 |
| OPR-018 | Regularization | F9 | 正则化 |
| OPR-019 | Stability Guarantee Addition | F8 | 补稳定性保证 |
| OPR-020 | Error-bound Addition | F8 | 补误差界 |

> 该集合是**开放集**：每读一批论文都应沉淀新算子或新 pattern card。

---

## 5. Research Pattern Card（`RPC-`）

Pattern card 是**从真实论文沉淀出的创新推理模式**，是算子库的经验来源（任务书第 18 节）。

### 5.1 Schema
```
RPC-xxx
  name*            模式名
  trigger*         何时触发（"既有理论要求条件 C，但真实系统不满足 C"）
  strategy*        核心策略（构造 T(P) 使 T(P) ⊨ C）
  operators[]      该模式通常组合使用哪些算子
  verification[]   该模式需要哪些验证义务
  source_papers[]  证据来源
  provenance*
```

### 5.2 范式示例：CCK 的 Structure Manufacturing

```yaml
id: RPC-001
name: Structure Manufacturing / Assumption Engineering
trigger: |
  既有理论要求结构条件 C（如常数控制矩阵 B），
  而真实问题 P 不满足 C。
strategy: |
  构造一个变换/增广 T，使 T(P) 满足 C，并证明原问题与增广问题的关系。
  形式化：P ⊭ C，T(P) ⊨ C。
operators:
  - OPR-004  # dynamic extension / virtual dynamics / prefilter
  - OPR-003  # state augmentation
  - OPR-005  # coordinate / input transformation
verification:
  - 证明 T(P) 满足 C
  - 证明增广系统与原系统的关系（等价/近似 + 误差）
  - 量化新增动态带来的代价
  - 与原始 formulation 做仿真对比
source_papers: [PAP-011]   # CCK
```

### 5.3 抽象模式
```
Restrictive Assumption
  → Structural Obstruction
  → Problem Transformation
  → Manufacture Desired Structure
  → Reuse Existing Theory
```

---

## 6. 从论文到算子的沉淀流程

```
Paper (PAP) ──> Structure Extractor (A4) 抽出 function/assumptions/limitation/innovation pattern
           ──> Gap/Assumption Miner (A6) 抽出可复用 gap 形态
           ──> Pattern Card 提名（RPC- proposal）
           ──> 与既有算子/卡片去重（相似度 + 人工/复核确认）
           ──> 接纳为新 OPR 或 RPC，建立 references
```

**约束（与 vibe 蒸馏一致）**：一次观察不得直接变成全局规则；pattern card 需要**重复证据**或**用户/复核批准**才从候选转为 active。候选卡片状态建议复用 vibe 的 `distillation` 语义（`candidate → approved → encoded`）。

---

## 7. 算子驱动的 idea 批量生成

任务书第 6 节的核心机制：

```
Gap × Operator → 一批候选 idea
```

- 对每个 `GAP-x`，遍历适用算子（由 `preconditions` 过滤），生成 `IDEA-y`。
- 每个 idea 必须记录 `origin.innovation_operator`（`01` 第 4.7 节 Idea 的 `origin` 字段）。
- 生成前必须检索 FailureMemory；命中相同思路必须引用 `salvages` 或说明差异。
- 生成后立刻进入 `04` 的四类检查，不做"先攒够再筛"。

**反模式**：把 20 个算子在 prompt 里一次性丢给 LLM 要求"综合创新"——这会丧失可审计性。必须逐 `(gap, operator)` 对生成。

---

## 8. 质量、去重与演化

| 方面 | 规则 |
|---|---|
| 去重 | 新卡片需与既有卡片做语义相似度检查；重复的合并并记录 `supersedes` |
| 有效性 | 卡片必须附 `source_papers` 与 `verification`；无来源的卡片只能停留在 `candidate` |
| 演化 | 算子可被细化（拆分子算子）或泛化；演化记录为 `derives-from` |
| 淘汰 | 长期未被任何 idea 采用、或导致多次失败的算子标记 `deprecated`（保留历史） |

---

## 9. 开放问题

- `OQ-11` Research Pattern Card 的"重复证据"门槛（多少次独立观察 / 是否需要人工批准）。
- `OQ-12` 算子去重是用确定性相似度还是 LLM 判定，以及是否需要人工复核。
- `OQ-13` 算子库的初始规模（仅 20 个起步 vs 先人工沉淀一批领域卡片）。
