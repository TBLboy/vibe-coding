# 01 · Research State Schema

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 4.2、12 节  
> 下游依赖：`02`（角色读写权限）、`07`（证据与 provenance）、`08`（MVP-0 产物）

---

## 1. 目的

定义整个系统的**唯一结构化事实源**。核心原则（任务书第 12 节）：**不把聊天记录当作系统核心状态**。所有实体、关系、状态与 provenance 都必须落在 Research State 中，并可被机器校验。

## 2. 存储模型（两层，复用 vibe 的既有做法）

| 层 | 内容 | 位置 | 说明 |
|---|---|---|---|
| **结构化事实** | 实体实例、关系、状态、provenance、证据绑定 | `.project-log` 状态库（Project Log format 2，SQLite store schema 3） | 唯一事实源，机器可读、可校验 |
| **长正文** | 论文笔记、proof 全文、实验报告、图 | `.project-log/docs/auto-research/**` 或 run 产物目录 | 结构化记录只保存 `doc_ref`（路径 + 内容哈希） |

> **约束**：不得出现第二套"只存在于 agent 上下文"的事实。任何进入下游的结论都必须先落库。

## 3. ID 命名空间

为避免与 vibe 既有 ID（`TASK-/RUN-/DEC-/GOAL-/SC-/EV-`）冲突，领域 ID 使用独立前缀：

| 前缀 | 实体 | 前缀 | 实体 |
|---|---|---|---|
| `RB-` | ResearchBrief | `TH-` | TheoryNode |
| `BR-` | Research Branch | `EXP-` | Experiment（设计） |
| `PAP-` | Paper | `XRUN-` | Experiment Run（执行） |
| `ASM-` | Assumption | `CLM-` | Claim |
| `GAP-` | Gap | `EVD-` | Evidence（领域证据对象） |
| `OPR-` | InnovationOperator | `FAIL-` | FailureMemory |
| `RPC-` | ResearchPatternCard | `ART-` | Artifact |
| `IDEA-` | Idea | | |

ID 形如 `IDEA-007`，项目内全局唯一、只增不减、**永不复用**。

## 4. 实体与字段

字段标记：`*` = 必填，`?` = 可选，`{}` = 子结构。

### 4.1 ResearchProject
```
id*, statement*, domain[], research_style[], allowed_contributions[],
experiment_type[], constraints{}, created_at*, provenance*
```
顶层容器，聚合下列全部实体。与 vibe project 一对一绑定。

### 4.2 ResearchBrief（`RB-`）
```
id*, project_id*, domain[], research_style[], allowed_contributions[],
experiment_type[], seed_idea?, constraints{ novelty_required, theorem_required,
reproducibility_required }, provenance*
```
由 Problem Framer 从用户输入结构化而来（任务书第 5.2 节）。

### 4.3 Research Branch（`BR-`）
```
id*, project_id*, parent_branch?, status, root_idea*, budget{}, provenance*
status ∈ {open, active, frozen, killed, promoted}
```
研究树的分支单元。`promoted` = 进入下一阶段；`killed` = 被 Kill Criteria 淘汰但保留。

### 4.4 Paper / LiteratureCorpus / PaperGraph
```
PAP: id*, title*, authors[], year*, venue?, doi?, url?, pdf_ref?,
     structured{}, provenance*
LiteratureCorpus: project_id*, paper_ids[], updated_at*
PaperGraph: nodes[PAP], edges[ {from,to,relation} ]
```
`structured` 承载 Literature Structure Extractor 的抽取结果（任务书第 5.4 节）：
`problem, assumptions[], definitions[], main_theorems[], method, claimed_advantages[], limitations[], experimental_setting, future_work`。

### 4.5 Assumption（`ASM-`）与 Gap（`GAP-`）
```
ASM: id*, project_id*, source_paper?, statement*, kind, severity?, provenance*
     kind ∈ {structural, regularity, data, knowledge, computational, measurement}
GAP: id*, project_id*, from_assumptions[], kind*, statement*,
     evidence[], related_papers[], provenance*
     kind ∈ {restrictive_assumption, missing_guarantee, contradiction,
             weak_evaluation, robustness, computational, finite_data, model_mismatch}
```

### 4.6 InnovationOperator（`OPR-`）与 ResearchPatternCard（`RPC-`）
```
OPR: id*, name*, family*, signature*, preconditions[], transform*,
     expected_effect*, references[], provenance*
RPC: id*, name*, trigger*, strategy*, operators[], verification[],
     source_papers[], provenance*
```
见 `03_innovation_operator_library.md`。

### 4.7 Idea（`IDEA-`）
```
id*, project_id*, branch_id*, parent_id?, problem*, core_claim*,
origin{ source_papers[], target_gap?, target_assumption?, innovation_operator? },
required_assumptions[], expected_theorem?, expected_experiment?,
novelty_evidence[], prior_art_risk,
failure_memory_check{ at, hits[], note },   # 创建时必填（不变量 10）
failure_reason?,                            # 仅 status=killed 必填（不变量 6）
status*, checks{}, provenance*
status ∈ {proposed, screening, active, refined, killed, validated}
checks: { novelty, feasibility, significance, falsification }  # 每个为 {verdict, evidence[], at}
```

### 4.8 TheoryNode（`TH-`）
```
id*, project_id*, branch_id*, idea_id*, kind*, statement*,
depends_on[], assumptions[], proof_ref?, proof_status,
counterexamples[], verification{}, provenance*
kind ∈ {definition, assumption, lemma, theorem, corollary}
proof_status ∈ {none, draft, audited, challenged, verified, refuted}
verification: { symbolic?, numeric?, formal?, counterexample_search? }
```
见 `05_theory_engine.md`。

### 4.9 Experiment（`EXP-`）与 Experiment Run（`XRUN-`）
```
EXP: id*, project_id*, branch_id*, claim_refs[]*, hypothesis*,
     design{ baselines[], variables[], metrics[], fidelity }, expected_signal*,
     status, provenance*
XRUN: id*, experiment_id*, env{}, seed*, config_ref*, code_ref*,
      result_ref*, metrics{}, verdict, artifacts[], provenance*
verdict ∈ {smoke_pass, verify_pass, full_pass, failed, inconclusive}
```
`verdict` 与 `PROCEED/REFINE/PIVOT/KILL` 的映射见 `06`。

### 4.10 Claim（`CLM-`）
```
id*, project_id*, statement*, type*, evidence_refs[], verification*,
unresolved_reason?,   # 仅 status=unresolved 必填（不变量 4）
status*, provenance*
type ∈ {literature, theory, experiment, methodological}
status ∈ {proposed, supported, verified, rejected, unresolved, stale}
```
见 `07_evidence_and_provenance.md`。

### 4.11 Evidence（`EVD-`）
```
id*, kind*, subject*, status*, covers{}, version_binding{}, doc_ref?, provenance*
kind ∈ {literature, proof, symbolic, numeric, simulation, formal}
status ∈ {candidate, valid, failed, stale, superseded, invalid}   # 与 vibe 证据状态一致
```

### 4.12 FailureMemory（`FAIL-`）
```
id*, project_id*, idea*, why_promising*, attempt*, failure_reason*,
minimal_counterexample?, salvage_paths[], related_evidence[], provenance*
```
见 `07` 第 5 节与任务书第 11 节。

### 4.13 Artifact（`ART-`）
```
id*, project_id*, kind*, path*, sha256*, produced_by_run*, provenance*
kind ∈ {code, data, figure, table, proof_note, manuscript}
```

## 5. 关系（relations）

关系为有向边，登记在 `record_links` 风格的边表中：

| relation | from → to | 含义 |
|---|---|---|
| `derives-from` | Idea|Theory|Experiment → 上游节点 | 演化来源 |
| `uses-operator` | Idea → Operator | 使用了哪个创新算子 |
| `targets-gap` | Idea → Gap | 针对哪个 gap |
| `targets-assumption` | Idea → Assumption | 针对哪条假设 |
| `implements` | Theory → Idea | 理论实现了 idea |
| `tests` | Experiment → Claim | 实验检验哪条 claim |
| `supports` | Evidence → Claim | 证据支持 |
| `refutes` | Evidence|Counterexample → Claim|Theory | 证据反驳 |
| `supersedes` | any → any | 版本取代（链必须无环） |
| `kills` | Evidence|Check → Idea|Branch | 触发淘汰 |
| `salvages` | FailureMemory → Idea | 失败记忆复活出的新 idea |
| `references` | any → Paper | 文献引用 |

## 6. Provenance 信封（所有实体强制）

```
provenance*: {
  actor*,            # agent 角色 id 或 human
  generated_by*,     # 模型 id / 工具 id / deterministic-script
  based_on*,         # 依赖对象 id 列表（空列表仅允许 origin=observation）
  run_ref?,          # 关联的 XRUN- 或 vibe RUN-
  origin?,           # normal（默认）| observation（原始观测，如首次检索无命中）
  created_at*,
  verified*,         # bool
  verification_refs[], # EVD- 列表
  used_by[]          # 反向引用，由系统维护
}
```

## 7. 状态枚举汇总

- Branch：`open | active | frozen | killed | promoted`
- Idea：`proposed | screening | active | refined | killed | validated`
- proof_status：`none | draft | audited | challenged | verified | refuted`
- Claim：`proposed | supported | verified | rejected | unresolved | stale`
- Evidence：`candidate | valid | failed | stale | superseded | invalid`
- XRUN.verdict：`smoke_pass | verify_pass | full_pass | failed | inconclusive`

> 所有状态迁移必须是**显式事件**的结果，不允许被静默改写。MVP-0（S0–S6）的事件名见 `08` 第 3 节；Idea / Theory / Claim / Evidence 的迁移事件在对应阶段实现时定义，并遵循同一"显式事件"约束。

## 8. 机器校验规则（invariants）

以下不变量必须可被一个确定性校验器检查（实现为脚本，非 LLM）：

1. **唯一性**：所有 ID 在命名空间内唯一。
2. **引用完整性**：任何字段引用的 ID 必须存在；`based_on` 不得自引用。
3. **无环**：`derives-from`、`supersedes`、`parent_id` 构成的图必须无环。
4. **Claim 可追溯**：`status ∈ {verified, rejected, supported}` 的 Claim 必须至少有 1 个 `EVD-`；`status=unresolved` 允许无证据，但必须携带非空 `unresolved_reason`。
5. **定理完整性**：`TH.kind=theorem` 且 `proof_status=verified` 时必须满足：`proof_ref` 非空，且 `verification` 中 `symbolic`/`numeric`/`formal` 至少一项通过。
6. **Kill 完整性**：`Idea.status=killed` 必须携带 `failure_reason`，并写入 `FAIL-`。
7. **Writer 门禁**：进入稿件材料的 Claim 必须 `status=verified` 且证据非 stale。
8. **证据绑定**：`EVD.version_binding` 必须能定位到具体产物哈希；覆盖产物变化后证据转 `stale`（沿用 vibe 规则）。
9. **provenance 完整**：每个实体强制含 provenance；`based_on` 不得为空，除非 `provenance.origin=observation`（原始观测，例如首次检索无命中的记录）。
10. **失败记忆优先检索**：新 `IDEA-` 创建事件必须记录一次 `failure_memory_check` 结果（命中/未命中）。

## 9. 与 vibe 状态库的映射

| 本 Schema | vibe 载体 |
|---|---|
| 实体实例 | records（`record.create`，kind 建议新增 `idea/theory/experiment/claim/…` 或复用 `research` 泛化） |
| 关系 | record links（复用既有 relation 词表，必要时扩展） |
| Claim 证据 | evidence 记录（复用状态机与 stale 失效） |
| 复核 | review 记录（go/no-go/conditional） |
| 长正文 | `.project-log/docs/auto-research/**` + `doc_ref` |
| 分支推进/淘汰 | task/run 生命周期 + loop decision |

> **是否新增 vibe record kind 属于开放问题 `OQ-02`**：可选方案 A（新增领域 kind）、方案 B（复用 `research` kind + 子类型字段）。推荐 A，因为校验规则更清晰。

## 10. Schema 骨架（示意）

```json
{
  "idea": {
    "id": "IDEA-007",
    "project_id": "PRJ-001",
    "branch_id": "BR-003",
    "parent_id": "IDEA-004",
    "problem": "CCK 要求常数 Bp，而真实执行器给不出常数 B",
    "core_claim": "通过 virtual dynamics 可将系统增广为满足常数 B 的结构",
    "origin": {"source_papers": ["PAP-011"], "target_gap": "GAP-005", "innovation_operator": "OPR-002"},
    "required_assumptions": ["ASM-021", "ASM-022"],
    "status": "active",
    "checks": {"novelty": {"verdict": "uncertain", "evidence": ["EVD-031"], "at": "2026-09-26T09:00:00+08:00"}},
    "provenance": {"actor": "idea-generator", "generated_by": "…", "based_on": ["GAP-005"], "created_at": "…", "verified": true, "verification_refs": [], "used_by": []}
  }
}
```

## 11. 开放问题

- `OQ-02` 是否为 vibe 状态库新增领域 record kind，还是复用 `research` kind。
- `OQ-03` 领域实体是否全部进状态库，还是允许"轻量对象"（如 Gap）仅存文档并由索引引用。
- `OQ-04` `LiteratureCorpus` 与 `PaperGraph` 的规模上限与分页策略（影响检索性能）。
