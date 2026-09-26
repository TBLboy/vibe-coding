# 05 · Theory Engine

> 上级索引：[`README.md`](README.md)  
> 上游：任务书 v0.1 第 8 节  
> 依赖：`01`（TH 实体）、`02`（A12–A17）、`07`（证据状态）

---

## 1. 目的

Theory Engine 是与多数"AI Scientist"项目差异最大的部分（任务书第 8 节）：以**数学正确性**为中心，用**对抗式流水线**代替单次生成。目标不是"生成一个看起来像证明的文本"，而是让定理经历多轮独立攻击后仍存活，或明确被推翻。

---

## 2. 流水线

```
Theory Builder (A12)
      │  产出 Definitions / Assumptions / Theorem / Proof
      v
Assumption Auditor (A13)        校验假设完备性与必要性
      v
Proof Critic (A14)              独立审查（只读 statement + proof）
      v
Counterexample Hunter (A15)     定向寻找最小反例
      v
Symbolic / Numerical Checker (A16)  确定性校验
      v
Optional Formal Verifier (A17)  高价值定理的形式化
      v
  [ 通过 ] → TH.proof_status = verified
  [ 失败 ] → 回 Builder 修订 / 或触发 Idea 层 refine/kill
```

---

## 3. 独立性规则（硬性）

1. **A14 Proof Critic 不得读取 Builder 的内部推理过程**，只允许看到：`Definitions`、`Assumptions`、`Theorem`、`Proof`（任务书第 8.3 节）。
2. **A16 校验必须是确定性工具**（SymPy/NumPy/SciPy/CVXPY/python-control），不得由 LLM 代替。
3. **A15 允许读证明**（用于定向找反例），但其输出必须是**可复现的反例实例**，而非"我觉得有问题"。
4. 任一验证者的"未发现问题"**不等于**通过，除非同时给出**覆盖范围说明**。

---

## 4. 产物契约

### 4.1 Definitions
- 每个符号/空间/算子必须有明确定义域与类型。
- 不允许"显然/自然/类似"这类未定义的过渡。

### 4.2 Assumptions
- 逐条列出，且可判定"某条是否被实际使用"。
- 每条假设标注来源（继承自文献 / 新增 / 由 gap 决定）。
- 任务书第 8.2 节要求审计：continuity / compactness / differentiability 等条件是否**真的需要**；结论是否超出假设可支持的范围。

### 4.3 Theorem / Lemma / Corollary
```
TH-xxx (kind=theorem)
  statement*
  assumptions[]        # 引用 ASM- 或 TH-(definition)
  depends_on[]         # 引用的其他 TH-
  proof_ref*           # 指向 proof 文档
  proof_status*
  counterexamples[]    # 已找到的反例
  verification{ symbolic?, numeric?, formal?, counterexample_search? }
```

### 4.4 Proof 文档（长正文，doc_ref）
建议结构：
```
1. 目标 statement 复述
2. 使用的前提（definitions / assumptions / 引用的 lemma）
3. 证明主体（每步可定位）
4. 边界与退化情况
5. 与既有结果的关系（对应任务书 8.1：标注 theorem 与已有工作的关系）
6. 已知的薄弱步骤（Builder 自陈）
```

---

## 5. 定理状态机与失败语义

```
none → draft → audited → challenged → verified
                     └──────────────> refuted
```

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `none` | 尚未写证明 | 仅声明 theorem |
| `draft` | Builder 完成初稿 | 有 proof_ref |
| `audited` | Assumption Auditor 完成假设审计 | A13 无致命缺口 |
| `challenged` | Proof Critic 或反例猎手提出缺陷 | 存在未解决的 critique/counterexample |
| `verified` | 多轮攻击后存活 + 确定性校验通过 | A14 无缺陷 + A16 通过（高价值定理再加 A17） |
| `refuted` | 被反例或矛盾推翻 | 存在有效反例/矛盾 |

**失败归因**（复用 vibe 词表）：`specification`（定理陈述有误）、`functional-business-logic`（业务/数学目标定义错）、`implementation`（证明写错）、`technical-selection`（工具选错）、`verification-harness`（检查器本身有 bug）。

**回退路径**：
- 证明写错 → 回 A12（状态回 `draft`）。
- 定理陈述错 → 回 Idea 层 refine（`IDEA.status=refined`）。
- 假设不成立/反例有效且本质 → 触发 `04` 的 KC-04。

---

## 6. 反例搜索规范（A15）

优先级与最小化：
1. 最低维数：`n=1`，其次 `n=2`。
2. 解析函数族：`f(x)=x²`、`f(x)=sin x`、`f(x,u)=xu`。
3. 退化/奇异矩阵、边界参数。
4. 随机/Monte-Carlo 搜索（记录种子与预算）。

输出必须包含：最小实例、违反的具体步骤/结论、搜索覆盖范围。若未找到反例，标记反例搜索的**覆盖限度**（维度上限、参数网格），不得等价于"正确"。

---

## 7. 形式化验证（可选，MVP-1+）

- 只对**高价值 theorem**（进入最终材料、或关键依赖）启用。
- 目标：把自然语言证明逐步转为 Lean（或等价）验证任务（任务书第 16.9/16.10 节）。
- 不可行时显式标"未形式化"，**不降低**其他验证要求，也不因"未形式化"而 block MVP-0/1。

---

## 8. 与 vibe 工作流的映射

| 本文件概念 | vibe 机制 |
|---|---|
| A14/A16/A23 的独立性 | `verification-reviewer` 只读、独立复核契约 |
| proof_status 迁移 | 显式事件 → record 更新 |
| 确定性校验证据 | evidence（`kind=symbolic/numeric/formal`）|
| proof 全文 | `.project-log/docs/**` 长正文 + `doc_ref` |
| `verified` 需 go 复核 | 高风险 review 的 go/no-go/conditional |

---

## 9. 开放问题

- `OQ-05` A14 独立性级别（进程级 vs 记录级隔离）。
- `OQ-18` 何时启用形式化验证的门槛（哪些 theorem 算"高价值"）。
- `OQ-19` 是否需要引入证明助手（如 SymPy 之外）以及如何界定其可信边界。
- `OQ-20` 定理与既有结果的关系由谁维护（Builder 自陈 vs 独立 mapping）。
