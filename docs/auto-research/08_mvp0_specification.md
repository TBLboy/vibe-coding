# 08 · MVP-0 Specification

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 13、14 节  
> 依赖：`00`–`07` 全部

---

## 1. MVP-0 目标（任务书第 14 节）

> **输入**：一个控制/Koopman 主题，或一篇论文。  
> **输出**：自动产生**有文献支撑、经过初步证伪**的研究路线（2–3 条值得进一步推导的分支）。

MVP-0 = **Research Idea Engine**（`00` 第 6 节）。它是本系统的第一个可交付闭环，也是最适合首先做好的部分。

---

## 2. 范围

**包含**（任务书第 14 节）：
- literature mapping；
- assumption extraction；
- gap mining；
- innovation operators；
- idea portfolio；
- novelty check；
- preliminary falsification；
- 输出 2–3 个待推导分支。

**不包含**（推迟到 MVP-1+）：
- 完整定理/证明流水线（MVP-1，`05`）；
- 仿真执行闭环（MVP-2，`06`）；
- 论文编译（MVP-3）；
- 形式化验证（MVP-1 可选）；
- 跨项目 Research Memory（`OQ-26`）。

---

## 3. 状态机

```
S0 Problem Initialization
 │
 v
S1 Literature Mapping
 │
 v
S2 Structured Knowledge Extraction
 │
 v
S3 Gap / Assumption Mining
 │
 v
S4 Idea Generation
 │
 v
S5 Idea Screening (Novelty/Feasibility/Significance/Falsification)
 │\
 │ \--- failed ---> S4 (refine) 或 kill（生成 FAIL-）
 v
S6 Branch Export（2–3 条路线）
```

> 任务书第 13 节把 S5/S6 合并于其 `S5`；本规格拆出 S6 "Branch Export"，因为它是 MVP-0 的**可验收出口**。

### 状态 → 事件 → 产物绑定

| 状态 | 触发事件 | 执行角色 | 产物 |
|---|---|---|---|
| S0 | `project.initialized` | A1/A2 | `ResearchProject`、`RB-` |
| S1 | `literature.mapped` | A3 | `LiteratureCorpus`、`PAP-` |
| S2 | `papers.structured` | A4 | `PAP.structured` |
| S3 | `gaps.mined` | A6 | `ASM-`、`GAP-` |
| S4 | `ideas.generated` | A7 | `IDEA-`（~20） |
| S5 | `idea.screened` | A8–A11 | `checks{}`、kill 决策、`FAIL-` |
| S6 | `branches.exported` | A1 | 2–3 条 `BR-`（`promoted`/`frozen`）+ brief |

> 本表是 **MVP-0 专属**的阶段事件。Idea / Theory / Claim / Evidence 等实体级迁移事件不在 MVP-0 定义，将在对应阶段（MVP-1/2）补充；`01` 第 7 节的"显式事件"约束对它们同样成立。

---

## 4. 产物清单（MVP-0 交付）

| 产物 | 载体 | 说明 |
|---|---|---|
| ResearchBrief | `RB-` | 结构化输入 |
| LiteratureCorpus + PaperGraph | `PAP-` + 边 | 可查询的证据库，非摘要 |
| Assumption/Gap 集 | `ASM-`/`GAP-` | gap mining 结果 |
| Idea Portfolio | `IDEA-` | ~20 候选，含 status/checks |
| Screening 证据 | `EVD-` | novelty/feasibility/significance/falsification |
| 失败记忆 | `FAIL-` | 被 kill 的 idea + 反例 + salvage |
| 出口分支 | `BR-` ×2–3 | 每条附：核心 claim、所需假设、预期定理/实验、风险 |
| 运行报告 | 长正文 | `.project-log/docs/auto-research/runs/**` |

**出口分支最小内容**：`PROCEED` 所需的信息——core claim、target gap/operator、required assumptions、expected theorem、expected experiment、prior-art risk、下一步建议。

---

## 5. 验收标准（MVP-0）

| # | 标准 | 证据 |
|---|---|---|
| AC-1 | 给定一个主题/论文，S0–S6 全流程无人工干预可运行（允许人工 checkpoint 关闭时） | 一次完整 run 记录 |
| AC-2 | 抽检文献结论忠实原文（Literature accuracy） | 抽检对照表 |
| AC-3 | 假设抽取对给定论文可复现（同输入同输出，允许 LLM 但需固定配置） | 重复 run 对比 |
| AC-4 | 产出的 gap 非伪 gap（人工抽检 ≥ 阈值） | 抽检记录（阈值见 `OQ-07`） |
| AC-5 | Novelty 判定从不把"搜不到"当作"新"（必须 `uncertain`） | Ledger 抽查 |
| AC-6 | 每个出口分支都能追溯到 `GAP-`/`OPR-`，且能追溯到来源 `PAP-` | 引用完整性校验 |
| AC-7 | 被 kill 的 idea 均有 `FAIL-` 与 `failure_reason` | 校验器输出 |
| AC-8 | 出口分支数量 2–3，且有明确"下一步" | run 报告 |

> 具体数值阈值与基准集（AC-4 等）属于 `OQ-07`，实现前需用户批准。

---

## 6. 与 vibe 工作流概念的映射

| MVP-0 概念 | vibe 机制 |
|---|---|
| S0–S6 状态迁移 | task/run 生命周期 + loop decision |
| 每个状态事件 | 显式 record 提交（可审计、可回放） |
| Screening 的独立检查 | `verification-reviewer` 独立复核 |
| 出口分支 | 后续任务的 `depends_on` 节点 |
| Research State | `.project-log` 状态库 + 生成视图 |
| 失败记忆 | records + 长正文 doc_ref |
| 运行报告 | `.project-log/docs/auto-research/runs/**` |

**分支隔离**：本项目自身使用 git 分支 `opencode-auto-research`；但**研究项目**（Run 内的 ResearchProject）是否按研究分支隔离状态，是 `OQ-08`（与 vibe 的"按分支隔离状态"机制相关，需明确避免混用）。

---

## 7. 出口与下一步

MVP-0 完成后：

1. 每条 `promoted` 分支进入 MVP-1 的 `05` 理论闭环；
2. `frozen` 分支保留，供后续复活；
3. 复盘（vibe `a-retrospective`）：评估漏斗淘汰质量、伪 gap 率、失败记忆复用率；
4. 决定 MVP-1 的技术选型（`solution-research`）。

---

## 8. 开放问题（MVP-0 相关）

- `OQ-02` record kind 方案（影响状态库落地）。
- `OQ-07` 量化阈值与基准集。
- `OQ-08` 研究项目的分支隔离策略。
- `OQ-09` 人工 checkpoint 默认开关。
- `OQ-13` 算子库初始规模。
- `OQ-14` 多样性阈值。
- `OQ-26` 跨项目 Research Memory 是否需要在 MVP-0 就预留接口。
