# OPEN_QUESTIONS · 未决项总表

> 上级索引：[`README.md`](README.md)  
> 规则：**本表只登记未决项，不做静默决策。** 标注 `C` 的问题在进入对应阶段实现前，必须由用户明确批准；`B` 的问题由 Agent 决策并记录到 decision-log。

**状态**：全部 `open`（截至设计规格 v0.1）。  
**影响**：`C` = 产品语义/数据/安全/范围/不可逆；`B` = 可自主决定但值得追溯。

| ID | 问题 | 影响 | 推荐答案 | 阻塞阶段 | 出处 |
|---|---|---|---|---|---|
| OQ-01 | 初始垂直领域收窄到什么程度（仅 Koopman/CCK 单点 vs 更宽控制理论） | C | 先在 Koopman/CCK 单点跑通闭环，再横向扩展 | MVP-0 | `00` |
| OQ-02 | 是否为 vibe 状态库新增领域 record kind（idea/theory/claim/failure） | B | 方案 A：新增领域 kind，校验规则更清晰 | MVP-0 实现 | `01`,`08` |
| OQ-03 | Gap/ASM 等"轻量对象"是否全部进状态库 | B | 全进，保证引用完整性；仅正文进文档 | MVP-0 实现 | `01` |
| OQ-04 | LiteratureCorpus/PaperGraph 规模上限与分页策略 | B | 先支持数千篇，建索引与分页，避免全量载入 | MVP-0 | `01` |
| OQ-05 | A14 Proof Critic 的独立级别（记录级 vs 进程级/换模型） | B | 记录级起步；关键定理升级为换模型/独立会话 | MVP-1 | `02`,`05` |
| OQ-06 | A5/A8 对抗轮数上限与预算比例 | B | 每 idea 最多 2 轮对抗，预算 ≤ 该阶段 30% | MVP-0 | `02` |
| OQ-07 | MVP-0 量化验收阈值与基准集（AC-4 等） | C | 先设保守阈值 + 人工抽检 20 条，再据实调整 | MVP-0 | `00`,`06`,`08` |
| OQ-08 | 研究项目（ResearchProject）是否按研究分支隔离状态 | B | 复用 vibe 按分支隔离；研究分支映射到 task 而非 git branch | MVP-0 实现 | `08` |
| OQ-09 | 人工 checkpoint 默认开关（human copilot） | C | MVP-0 在 S3→S4 与 S5 出口设默认 checkpoint | MVP-0 | `00`,`02`,`08` |
| OQ-10 | A21 Claim Auditor 单点 vs 多审仲裁 | B | 单一权威 + 独立 review；关键 claim 加第二审 | MVP-0/1 | `02` |
| OQ-11 | Research Pattern Card 的"重复证据"接纳门槛 | B | 2 次独立观察或用户批准，方可 `approved` | MVP-0 后期 | `03` |
| OQ-12 | 算子去重方法（确定性相似度 vs LLM） | B | 确定性相似度初筛 + LLM 复核 + 人审关键项 | MVP-0 后期 | `03` |
| OQ-13 | 算子库初始规模 | B | 20 个通用算子 + 人工沉淀约 10 张领域 pattern card | MVP-0 | `03`,`08` |
| OQ-14 | 多样性强制的阈值与度量 | B | 任一 gap/算子族在 S1 存活集中占比 ≤ 40% | MVP-0 | `04`,`08` |
| OQ-15 | KC-06 的 N 与"证据签名"定义 | B | N=3；签名 =(假设集, 证据集, 失败类别) 三元组不变 | MVP-0 | `04` |
| OQ-16 | Novelty=`uncertain` 的 idea 能否进入 active | C | 允许进入 active，但禁止进入最终材料且强制标注不确定性 | MVP-0 | `04` |
| OQ-17 | Kill 是否需申诉/复核窗口 | B | O4 及以上成本的 kill 需一次廉价 appeal | MVP-0 | `04` |
| OQ-18 | 形式化验证的启用门槛 | B | 仅对进入最终材料的关键定理启用 | MVP-1 | `05` |
| OQ-19 | 证明助手选型与可信边界 | B | SymPy/数值起步；Lean 作为可选高价值层 | MVP-1 | `05` |
| OQ-20 | 定理与既有结果的关系由谁维护 | B | Builder 自陈 + 独立 mapping 复核 | MVP-1 | `05` |
| OQ-21 | 多 seed 数量与统计显著性判据 | B | ≥5 seeds，报告中位数与区间 | MVP-2 | `06` |
| OQ-22 | 实验沙箱边界（资源/网络/安全） | C | Docker 隔离 + 资源与网络限制，禁止无限制外联 | MVP-2 | `06` |
| OQ-23 | computational cost 是否纳入裁决 | B | 仅作报告项，不作主裁决，避免奖励低成本低质量 | MVP-2 | `06` |
| OQ-24 | `FAIL-` 与 `CLM.rejected` 的关系 | B | 失败记忆独立保留；rejected claim 可在 Limitations 引用 | MVP-1 | `07` |
| OQ-25 | Writer 门禁的实现位置 | B | 关卡脚本 + review 契约双保险 | MVP-3 | `07` |
| OQ-26 | 跨项目 Research Memory 是否纳入 MVP-0 | C | MVP-0 仅预留接口，不实现累积记忆 | MVP-0 | `07`,`08` |

---

## 决策记录映射

本规格集设计阶段已做的 B 级决策（需写入 decision-log）：

- **DEC-025**：新分支 `opencode-auto-research` 采用"复用 vibe 工作流为引擎 + 新增科研应用层"的定位，本轮仅交付设计规格。
- **DEC-026**（建议）：设计规格文档集置于仓库 `docs/auto-research/`，以 `README.md` 为索引。

> 上述 C 级问题（OQ-01/07/09/16/22/26）在获得用户批准前，不得据此进入实现。
