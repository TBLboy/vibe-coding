# 04 · Idea Search & Kill Criteria

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 4.1、7、19.1、19.3 节  
> 依赖：`01`（Idea/Gap/OPR）、`02`（A5/A7/A8–A11）、`03`、`07`（失败记忆）

---

## 1. 目的

任务书第 4.1 节：一次产生多个 candidate idea，而不是"从一个 idea 一路硬做到底"。本文件定义：

1. Idea 的**生命周期状态机**；
2. idea 的**生成策略**与剪枝节奏；
3. 四类独立检查的**可执行判据**；
4. **Kill Criteria**——独立于"想继续做"的淘汰规则（任务书第 19.3 节：防止 Agent 不愿放弃错误 idea）。

---

## 2. Idea 生命周期状态机

```
            ┌────────────────────────────────────────────┐
            v                                            │
proposed ──> screening ──(全部检查通过)──> active ──> refined ──> validated
   │            │                             │  ^          │
   │            │(任一硬性 kill)               │  └─(反馈修订)┘
   │            v                             v
   └────────> killed <──────────────────── (理论/实验失败)
                │
                └──> FAIL- (FailureMemory) ──> 可能复活为新的 proposed idea
```

状态定义见 `01` 第 7 节。**关键规则**：`active → refined` 与原状态之间是可回退的；`killed` 是**终态但可被 salvage**（不是遗忘）。

---

## 3. 生成策略与剪枝节奏

任务书第 4.1 节给出节奏：`20 → 8 → 4 → 2 → 1`。

| 轮次 | 动作 | 输入 | 输出 | 判据 |
|---|---|---|---|---|
| G1 | 批量生成 | Gap × Operator（`03` 第 7 节） | ~20 个 `proposed` | 覆盖多个 gap/算子族，强制多样性 |
| S1 | 廉价筛查 | 四类检查的低成本档 | ~8 个 `screening→active` | 见第 4 节 |
| S2 | 文献深化 | 对存活者做定向 prior-art 与可行性分析 | ~4 | A5/A9 |
| S3 | 反例/小实验 | 对 core claim 做低维证伪 | ~2 | A11 |
| S4 | 理论预演 | 骨架证明可行性 | 每漏斗 ~1 | A12 预演 |
| 出口 | 分支产出 | 每条漏斗出口 1 条路线；MVP-0 合计 2–3 条 | `promoted`/`frozen` | 见 `08` |

**漏斗粒度**：`20→8→4→2→1` 是**单条漏斗**的节奏。MVP-0 出口要求 2–3 条路线，因此需并行维护 **2–3 条以 Gap 聚类为单位**的独立漏斗（各自 20→…→1），而不是把一条漏斗的终值拆成 2–3 条。若资源只够一条漏斗，则减小 G1 生成量并向用户说明出口只有 1 条（复核标 `conditional`）。

**多样性强制**：S1 后任一 gap 或算子族占比不得超过阈值（`OQ-14`），避免"同一想法换皮"。

---

## 4. 四类检查（可执行判据）

每条检查产出 `verdict ∈ {pass, fail, uncertain}` + 证据 id。**检查者必须与生成者 A7 不同角色**（A8–A11）。

### 4.1 Novelty Check（A8/A5 对抗）
| 判据 | 判定 |
|---|---|
| 找到**等价**工作（方法/结论实质相同，仅换符号） | `fail` |
| 是已知理论的**直接特例** | `fail` |
| 找到**相关但非同质**工作，差异可陈述 | `pass`（差异必须写成可反驳的 claim） |
| 多库检索无命中 | `uncertain` —— **永远不等于 pass** |

> 任务书第 19.1 节：不能因为搜索不到就认为"没人做过"。必须多数据库 + citation graph + 同义扩展 + related-method 搜索 + adversarial prior-art。`uncertain` 必须带不确定性标签与检索式证据。

### 4.2 Feasibility Check（A9）
| 判据 | 判定 |
|---|---|
| 存在明显数学矛盾 / 假设不可同时满足 | `fail`（硬 kill） |
| 依赖无法满足或无法验证的假设 | `fail` 或 `uncertain` |
| 定理骨架可写出且无明显矛盾 | `pass` |
| 完全无法评估 | `uncertain` |

### 4.3 Significance Check（A10）
| 判据 | 判定 |
|---|---|
| 只是引入额外复杂度而无实际收益 | `fail` |
| 解决的问题无实际/理论意义 | `fail` |
| 提供了更强的 generality / 更弱假设 / 更清晰保证 | `pass` |
| 收益依赖尚未验证的实验假设 | `uncertain` |

> 维度：generality、practical relevance、theorem strength、experimental distinguishability、complexity cost、relation to strong baselines（任务书第 19.4 节）。

### 4.4 Falsification Check（A11）
| 判据 | 判定 |
|---|---|
| 找到低维反例破坏 core claim | `fail`（转 refine 或 kill） |
| 找到极端参数使 claim 失败 | `fail`/`uncertain` |
| 简单 case 已被检验且通过 | `pass` |
| 未搜索到反例 | `uncertain`（记录搜索空间） |

**最少反例搜索集**：`n=1,2`；`f(x)=x², sin x, f(x,u)=xu`；退化矩阵；奇异情况；边界情况（任务书第 8.4 节）。

---

## 5. Kill Criteria（可执行规则）

Kill 必须由**独立执行者**触发（Director 依证据、或确定性脚本），不能由 idea 的提出者自行决定。每条 kill 产生 `kills` 关系与一条 `FAIL-`。

| ID | 条件 | 所需证据 | 触发者 | 结果迁移 |
|---|---|---|---|---|
| KC-01 | Feasibility = fail（数学矛盾/假设不可满足） | 反例或矛盾证明 | A9 + 确定性校验 | `killed` |
| KC-02 | Novelty = fail（找到等价 prior-art） | prior-art 证据 | A5 | `killed` |
| KC-03 | Significance = fail（无实际收益/纯换皮） | significance 报告 | A10 | `killed` |
| KC-04 | Falsification = fail（core claim 被反例破坏） | 最小反例 | A11/A15 | `refined` 或 `killed` |
| KC-05 | 预算耗尽且未过 S 轮出口 | 预算账目 | A1 | `frozen` |
| KC-06 | 连续 N 轮无正向证据，且假设/证据签名未变 | delta 记录 | A1 + Loop Control | `killed` |
| KC-07 | 分支被同项目更优分支支配（同 gap，证据更强） | 对比证据 | A1 | `frozen` |

**KC-06 是防"沉没成本"的核心**：重试必须给出可证伪假设、相对上次的 delta 与预期证据；失败签名与 delta 均未变化时禁止重试（沿用 vibe Loop Control 的 retry contract）。

**Kill 记录义务**：`killed` 必须写 `failure_reason`；若存在最小反例必须写入 `FAIL.minimal_counterexample`；并给出 `salvage_paths`。

---

## 6. 复活机制（Failure Memory → Idea）

任务书第 11 节：失败研究是一等公民。规则：

1. 任何新 `IDEA-` 在创建前**必须**检索 FailureMemory（`01` 不变量 10）。
2. 命中同一思路时：要么引用 `salvages` 作为父 idea，要么显式陈述"与失败记录的差异"（差异本身要可检验）。
3. `salvage_paths`（如 CCK 例中的 bilinear Koopman / dynamic extension / virtual input / input transformation）可被直接转化为新 `(gap, operator)` 对。

---

## 7. 预算与成本梯度

任务书第 19.5 节：budget-aware search。

```
O1 cheap literature screen
O2 cheap counterexample
O3 small simulation
O4 full simulation
O5 expensive formal / large experiment
```

- S1 只允许 O1/O2；S3 允许 O3；只有 `active` 的核心 claim 才允许 O4；O5 需 Director 显式批准。
- **禁止**对大量低质量 idea 直接投入最高成本档。

---

## 8. 与 vibe 工作流的映射

| 本文件概念 | vibe 机制 |
|---|---|
| Idea 状态机的每次迁移 | 显式事件 → record 更新 |
| Kill 决策 | loop decision `KILL` + `task.cancel` 语义 |
| KC-06 的防沉没成本 | Loop Control 的 retry contract |
| 检查者的独立性 | `verification-reviewer` 独立复核 |
| FailureMemory | `.project-log` 记录 + 长正文 doc_ref |

---

## 9. 开放问题

- `OQ-14` 多样性强制的具体阈值与度量（按 gap / 算子族 / 语义聚类）。
- `OQ-15` KC-06 中 N 的取值与"证据签名"的精确定义。
- `OQ-16` Novelty 的 `uncertain` 是否允许进入 active（推荐允许，但强制标注并限制其进入最终材料）。
- `OQ-17` Kill 是否需要人工复核/申诉窗口（推荐：O4 以上成本的 kill 需要一次 cheap appeal）。
