# 06 · Experiment Engine

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 9、16.7、16.8 节  
> 依赖：`01`（EXP/XRUN/ART）、`02`（A18–A20）、`07`（claim/证据）

---

## 1. 目的

实验不能是"随便选一个 pendulum 跑一下"（任务书第 9 节）。本文件定义：**每个实验都必须绑定一条 claim**，且裁决由**确定性评估**做出，而不是由 LLM 自评。任务书第 16.7 节的核心迁移原则：

```
LLM 负责提出修改/假设，deterministic evaluation 负责裁决。
```

---

## 2. claim-driven 原则（硬性）

- `EXP.claim_refs` 非空才有效；无 claim 的实验直接判为无效（`04` 第 5 节之外，另在 `06` 校验）。
- 实验的目的只有一个：为某条 `CLM-` 提供支持或反驳的证据。
- 不允许"先跑再想 claim"。

示例（任务书第 9 节）：claim = "Proposed method 对 state-dependent input matrix 的结构偏离更鲁棒"，则设计：
```
B_α(x) = B_0 + α·B_1(x),  α = 0, 0.1, …, 1
```
比较 baselines，输出 `error vs assumption violation` 曲线，而不是孤立 demo。

---

## 3. Experiment 契约

```
EXP-xxx
  id*, project_id*, branch_id*
  claim_refs[]*        # 被检验的 claim（引用 CLM-）
  hypothesis*          # 可证伪的预期信号
  design{
    baselines[],       # 对照方法
    variables[],       # 扫描/控制变量
    metrics[],         # 指标与符号方向
    fidelity           # smoke | verify | full
  }
  expected_signal*     # 什么结果算支持/反驳
  status               # designed | running | done | abandoned
  provenance*
```

**Common baselines（控制/Koopman 领域，任务书第 9 节）**：DMDc、standard Koopman with control、bilinear Koopman、original CCK、proposed。

**Common metrics**：one-step prediction error、rollout prediction error、closed-loop tracking error、LQR/MPC cost、robustness、computation time。

---

## 4. 实验 Funnel（预算梯度）

任务书第 16.8 节（Scholar Loop）的启发：smoke → verify → full。

| 档 | 名称 | 预算 | 目的 | 通过条件 |
|---|---|---|---|---|
| E0 | smoke | 极小 | 代码能跑通、指标能算 | 无异常、产出占位结果 |
| E1 | verify | 小 | 在缩小规模上检验信号方向 | 预期信号方向正确 |
| E2 | full | 大 | 完整规模、多 seed、多 baseline | 统计显著且可复现 |

规则：
- 不通过 E1 不得进入 E2。
- E2 必须多 seed，记录每 seed 与聚合统计。
- 任何档位失败都要归因（`implementation/environment/...`），禁止跳过。

---

## 5. 确定性评估与可复现

`XRUN-xxx`
```
id*, experiment_id*, env{ os, python, 关键库版本 }, seed*,
config_ref*, code_ref*,          # code/配置的哈希
result_ref*, metrics{},
verdict*, artifacts[], provenance*
```

可复现要求（MVP-2 成功度量之一）：
1. 固定随机种子，且记录种子；
2. 代码与配置可寻址（内容哈希）；
3. 原始数据、图表、日志作为 `ART-` 保存；
4. 结果可被独立重跑复现（复核者不复用实现者的结论）。

**硬规则**：任何"更好"的结论必须附带**对照 baseline 的确定性数值**；只有相对提升而无绝对数值的结论不予采信。

---

## 6. verdict 与 loop decision

| XRUN.verdict | 含义 | 映射到 loop decision |
|---|---|---|
| `smoke_pass` | E0 通过 | 继续 E1 |
| `verify_pass` | E1 方向正确 | 继续 E2 |
| `full_pass` | E2 支持 claim | `PROCEED`，claim → supported/verified（交 A21） |
| `failed` | 实现/环境失败 | `REFINE`（重试，须满足 retry contract） |
| `inconclusive` | 结果不足以判定 | `REFINE`（改设计）或 `PIVOT` |
| （设计本身弱） | 测试不出 claim | `REFINE`（改实验设计） |
| （claim 被反驳） | 负证据 | 见第 7 节 |

`PROCEED / REFINE / PIVOT / KILL` 与 vibe loop decision 词表一致；`KILL` 走 `task.cancel` 语义 + `04` 的 KC。

---

## 7. 负证据的处理（任务书第 3、10 节）

负结果是合法结果，必须归档：

1. **实验反驳 claim** → `CLM.status=rejected`，证据保留（不删除）。
2. **反驳指向设计缺陷** → `REFINE` 实验设计，claim 保持 `unresolved`。
3. **反驳指向理论问题** → 回 `05`（`TH` 回退）或 `04`（idea refine/kill）。
4. **`rejected` 与 `unresolved` 必须保留在 Claim Ledger 中**，防止后续 Agent 再次无依据地提出相同结论（任务书第 10 节）。

**对抗实验**：A19 Adversarial Experimenter 专门寻找方法失效场景（极端 α、分布外、噪声、退化），其负结果与正面结果**同权**进入 Ledger。

---

## 8. 与 vibe 工作流的映射

| 本文件概念 | vibe 机制 |
|---|---|
| EXP/XRUN | task/run 生命周期；每个 E 档可作为一个 run |
| 确定性裁决 | 测试/命令证据（命令 + 期望值） |
| metrics/figures | `ART-` + evidence 绑定哈希 |
| 失败重试 | Loop Control retry contract（hypothesis/delta/expected evidence） |
| 负证据保留 | evidence 状态 `failed` 保留，不删除 |

---

## 9. 开放问题

- `OQ-07` MVP-0 的量化阈值（本文件主要服务 MVP-2，但 E0 的"能跑通"判据在 MVP-0 就会用到）。
- `OQ-21` 多 seed 的数量与统计显著性判据（是否要求置信区间）。
- `OQ-22` 实验代码沙箱边界（Docker/资源限制/安全）。
- `OQ-23` "computational cost" 类指标是否纳入裁决，以及如何避免奖励低质量但低成本的方案。
