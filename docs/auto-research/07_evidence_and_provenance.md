# 07 · Evidence & Provenance

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 10、11、12 节  
> 依赖：`01`（CLM/EVD/FAIL/provenance）、`05`、`06`

---

## 1. 目的

任务书第 10 节：最终 Writer 原则上**只允许使用已验证的 claim**；`rejected` 与 `unresolved` 也必须保留。本文件定义：

1. **Claim Ledger** 的结构与状态机；
2. **Evidence** 模型及其与 vibe 证据状态机的统一；
3. **Provenance** 的统一要求；
4. **Failure Memory / Idea Graveyard** 的结构；
5. **Writer 门禁**的可执行规则。

---

## 2. Claim Ledger

`CLM-` 结构见 `01` 第 4.10 节。状态机：

```
proposed
   │ 获得 ≥1 valid 证据
   v
supported ── go 复核通过 ──> verified
   │                            │
   │ 出现有效反驳证据            │ 覆盖产物变化
   v                            v
rejected                       stale
                                │ stale 且失去全部有效证据
                                v
                           unresolved ── 补新证据 ──> supported / verified
```

> `proposed` / `supported` / `verified` 均可在出现有效反驳证据时转 `rejected`；`stale` 的判定与 `stale → unresolved` 规则见第 8 节。

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `proposed` | 提出但无证据 | 默认初始 |
| `supported` | 有支持证据但尚未独立复核 | ≥1 valid 证据 |
| `verified` | 独立复核通过且证据非 stale | `supported` + go 复核 |
| `rejected` | 被有效证据/反例反驳 | 存在 refutes 证据 |
| `unresolved` | 证据不足或结果不一致 | 必须记录非空 `unresolved_reason`（见 `01` 不变量 4） |
| `stale` | 覆盖产物已变化 | 证据失效时自动转 |

**Ledger 示例（任务书第 10 节）**：

| Claim | Type | Evidence | Verification | Status |
|---|---|---|---|---|
| Existing method requires constant B_p | literature | cited paper | citation checked | verified |
| Proposed augmentation yields constant B | theory | Theorem 1 | proof audit | verified / pending |
| Global stability holds | theory | Theorem 2 | counterexample search | rejected |
| Proposed method improves rollout prediction | experiment | Exp-04 | reproducible run | verified |
| Method always beats bilinear Koopman | experiment | Exp-07 | mixed results | unresolved |

---

## 3. Evidence 模型

`EVD-` 结构见 `01` 第 4.11 节。证据状态**直接复用 vibe** 的状态机，不新造：

```
candidate | valid | failed | stale | superseded | invalid
```

| 状态 | 含义 |
|---|---|
| `candidate` | 已登记但未验证 |
| `valid` | 已验证、可绑定产物 |
| `failed` | 产生过程失败或结论为负（**保留，不删**） |
| `stale` | 所覆盖产物字节已变化（沿用 vibe 失效规则） |
| `superseded` | 被更新的证据取代 |
| `invalid` | 证据本身不合法（如引用错误、环境伪造） |

**版本绑定**：`EVD.version_binding` 必须能定位产物哈希（`file_hashes` / `git_commit` / `diff_hash`）。**覆盖产物变化后必须转 `stale`，不能删除旧证据掩盖失效**（与 vibe 一致）。

---

## 4. Provenance

统一信封见 `01` 第 6 节。此处强调三点：

1. **强制**：每个实体必须有 provenance；缺失即校验失败。
2. **可追问到源头**：任意 claim 应能沿 `based_on` / `supports` 反向追溯到文献原文、证明步骤或实验数据。
3. **模型与 run 可辨**：必须记录 `generated_by`（模型/工具 id）与 `run_ref`，以支持"同一结论不同模型是否一致"的审计。

---

## 5. Failure Memory / Idea Graveyard

`FAIL-` 结构见 `01` 第 4.12 节。任务书第 11 节示例：

```yaml
idea: "把 state-dependent B(x)u 提升为常数-B 线性 Koopman 模型"
why_promising: "可保留 LTI 提升控制结构"
attempt: "把 B(x) 分量纳入可观测字典"
failure_reason: "输入与提升状态相乘，一般结果为双线性而非线性"
minimal_counterexample: "x_next = x + x·u"
salvage_paths:
  - bilinear Koopman
  - dynamic extension
  - virtual input
  - input transformation
```

规则：
- 每个 `killed` idea 必须生成 `FAIL-`（`01` 不变量 6）。
- 新 idea 生成前必须检索（`01` 不变量 10）。
- `salvage_paths` 是**下一轮 `(gap, operator)` 对的直接来源**。

> 长期看，失败知识库可能比成功论文集合更有价值（任务书第 11 节）。

---

## 6. Writer 门禁（可执行）

Paper Writer（A22）**只**允许消费满足全部条件的 claim：

1. `CLM.status = verified`；
2. 其全部证据 `status = valid` 且非 `stale`；
3. `provenance` 完整；
4. 无未解决的 refutes 证据。

**拒绝**：`supported`（未独立复核）、`unresolved`、`rejected`、`stale` 均不得进入稿件正文。

- 若某段材料不足，Writer 必须留下 `[NEEDS-EVIDENCE]` 标记，不得用语言润色掩盖空缺。
- `rejected` / `unresolved` 可在"Limitations / Negative results"章节**显式引用**，但不得作为正面结论。

这一门禁是可校验的：独立校验器遍历稿件 claim 引用，任何违反即判失败（`02` A23 的 GO/NO-GO 依据）。

---

## 7. 与 vibe 状态库的映射

| 本文件概念 | vibe 机制 |
|---|---|
| `CLM-` | records（kind 建议 `claim` 或研究子类型，见 `OQ-02`） |
| `EVD-` | evidence 记录（状态机与 stale 失效完全复用） |
| `FAIL-` | records（kind 建议 `failure` 或研究子类型） |
| 引用完整性 / 无环 | 复用 validator（`01` 第 8 节不变量） |
| Writer 门禁 | `vibe gate` 风格的前置检查脚本 |
| 复核 verdict | review（`go/no-go/conditional`） |

---

## 8. 失效与刷新

- 覆盖产物变化 → 相关 `EVD-` 自动 `stale`（沿用 vibe PostToolUse 精确失效机制）。
- `stale` 后：`CLM-` 若因此失去全部有效证据 → 转回 `unresolved`（不得保留 `verified`），并**自动写入** `unresolved_reason`（例如"全部证据转 stale"），以满足 `01` 不变量 4。
- 修复后重新登记新证据，不覆盖旧记录（旧记录转 `superseded` 或保留）。

---

## 9. 开放问题

- `OQ-24` `FAIL-` 与 `CLM.rejected` 的关系（失败记忆是否随 claim 提交进最终材料）。
- `OQ-25` Writer 门禁的实现位置（关卡脚本 vs review 契约）。
- `OQ-26` 跨项目 Research Memory（任务书第 16.3 节 AgentRxiv 的累积研究）是否在 MVP-0 之外。
