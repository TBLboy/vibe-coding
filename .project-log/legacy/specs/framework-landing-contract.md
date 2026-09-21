# format 2 生产契约（TASK-034）

> 状态：frozen（TASK-034 产物）
> 依据：`REQ-001`、`DEC-009`、`BL-FRAMELAND-001..009`
> 边界：本文件只冻结语义与接口；实现由 TASK-035..TASK-044 承担。任何与本文冲突的实现都按缺陷处理，
> 需要改变语义时必须先改本文并重新记录决策，不得让代码静默改写契约。

## 1. 现状事实（冻结时的源码证据）

| 事实 | 位置 |
|---|---|
| 默认初始化复制旧格式模板，不生成 format 2 | `runtime/scripts/init_project.py` |
| format 2 初始化要求 `experimental: true` 且拒绝已有 `.project-log` | `runtime/scripts/state_context.py` |
| 存储实体只有 goals/tasks/runs/blockers/commands/events/projection_jobs/exchange | `runtime/scripts/state_store.py` |
| 迁移只有 `preview` 与 `rollback_bundle`，没有 apply | `runtime/scripts/state_migrate.py` |
| format 2 校验只调用 `Store.validate()` | `runtime/scripts/validate_project.py` |
| PostToolUse 对 format 2 直接短路 | `runtime/hooks/post_tool_use.py` |
| 规则资产仍指向 `init_project.py` 与 `loopctl` | `prompts/vibe-global-agent.md`、`skills/a-project-init/`、`docs/USAGE.md` 第 14 节 |

## 2. 格式标记与目录布局

### 2.1 标记

`.project-log/state-format.json` 是格式唯一判据，内容为单行 JSON：

```json
{"format": 2, "project_id": "<32 位小写十六进制>"}
```

- 新项目**只写**这两个字段；不再写 `experimental`。
- 读取端必须同时接受 `{"format","project_id"}` 与 `{"format","project_id","experimental":true}`
  （后者是转正前初始化的隔离测试项目），其他字段组合一律 `invalid_format`。
- `experimental` 只作为历史兼容被读取，**任何写入路径都不得再产生它**。

### 2.2 布局

```text
.project-log/
  state-format.json     格式判据（Git 跟踪）
  .state/               本机状态目录（.gitignore，不提交）
  .migration/           迁移 journal、备份与 staging（.gitignore，不提交）
  exchange/             Git 文本快照交换区（* -text，不合并）
  generated/            派生视图（可重建，不作为事实源）
  docs/                 长文档正文（Git 跟踪）
  legacy/               迁移后的旧格式留存与未映射历史（仅迁移产生）
  legacy/new-writes/    回退时保留的迁移后新写入（.gitignore，恢复用副本）
```

### 2.3 上下文

- Git 项目：状态库位于 `<absolute-git-dir>/vibe-state/<project_id>/<context_id>/state.sqlite3`。
- `context_id = sha256({root, git_dir, branch_hex})`，因此分支与 worktree 天然分离。
- 非 Git 目录：使用 `.project-log/.state`，`branch` 记为 `local`。
- 同名实体在不同上下文之间不得互相覆盖；跨上下文只允许显式快照交换。

## 3. 数据模型

### 3.1 状态机实体（专用表）

保留并扩展既有表；这些实体参与状态迁移或门禁，必须有约束而非自由 JSON。

**goals**：`id, title, status, extensions, created_sequence, updated_sequence`

- `status ∈ {draft, active, waiting-user, blocked, complete}`（现有实现只允许 `active`，需放宽）。
- `extensions` 必须能承载旧格式 `project-goal.schema.json` 的全部字段原样：
  `success_conditions[]`（含 `id/statement/status/evidence_refs`）、`non_goals[]`、`constraints[]`、
  `required_evidence[]`、`risk_level`、`created_at`、`updated_at`。

**tasks**：现有列不变，`status` 现有取值不变；`extensions` 承载旧格式
`task-list.schema.json` 的字段原样：`kind, phase, authority, owner, tags, priority, risk,
related_business_logic[], related_decisions[], depends_on[], blocked_by[], required_skills[],
spec_ref, inputs[], outputs[], plan[], done_when[], verification{}, result{}, acceptance_refs[]`。

**runs**、**blockers**：现有列与状态机不变。

**evidence**（新增）

| 列 | 约束 |
|---|---|
| `id` | 主键，非空 |
| `task_id` | 外键 → `tasks(id)`，可空（项目级证据） |
| `kind` | 非空 |
| `subject` | 非空 |
| `status` | `candidate/valid/failed/stale/superseded/invalid`，与 Loop Core 词表一致 |
| `covers` | JSON：`{files[], requirements[], tasks[]}` |
| `version_binding` | JSON：`{git_commit, diff_hash, file_hashes{}}` |
| `recorded_sequence` | 非空 |
| `invalidated_sequence` / `invalidation_reason` | 失效时成对写入，不删除历史 |

**reviews**（新增）

| 列 | 约束 |
|---|---|
| `id` | 主键 |
| `task_id` | 外键 → `tasks(id)` |
| `reviewer` | 非空；必须与实现者身份不同 |
| `verdict` | `go/no-go/conditional` |
| `scope` | JSON：覆盖的验收条目与产物 |
| `evidence_refs` | JSON 数组，必须指向 `evidence` |
| `created_sequence` | 非空 |

### 3.2 文档型实体（单一 `records` 表 + 链接表）

业务原子、需求基线、决策、架构、研究、对齐、复盘、蒸馏的生命周期是同构的
（`draft → active → superseded/archived`），载荷却是异构的。为它们各建一张表不会带来额外能力，
只会扩大约束维护面。因此冻结为一张带 `kind` 判别的表：

```text
records(kind, id, title, status, revision, payload, created_sequence, updated_sequence)
  PRIMARY KEY (kind, id)

record_links(from_kind, from_id, relation, to_kind, to_id, created_sequence)
  PRIMARY KEY (from_kind, from_id, relation, to_kind, to_id)
```

- `kind ∈ {business-atom, requirement, decision, architecture, research, alignment, retrospective, distillation}`
- `status` 取值按 kind 冻结：
  - `business-atom`：`draft/active/experimental/deprecated/archived/conflict`
  - `requirement`：`draft/active/superseded/archived`
  - `decision`：`proposed/active/experimental/rejected/superseded/archived`
  - `architecture`：`draft/active/superseded/archived`
  - `research`：`draft/complete/superseded/archived`
  - `alignment`：`open/resolved/accepted/archived`
  - `retrospective`：`draft/complete/archived`
  - `distillation`：`candidate/approved/rejected/encoded/archived`
- `relation ∈ {references, depends-on, supersedes, implements, verifies, derived-from, blocks, aligns}`
- `payload` 是 JSON 对象，上限 **16384 字节**；不得存放长文档正文（见第 4 节）。
- 命令层校验（不是表约束）：`decision` 且 `payload.authority == "C"` 时必须
  `payload.user_approval == "approved"`；`requirement` 必须带 `approval.status`。

### 3.3 ID 规则

沿用旧格式前缀，保证迁移可逐项对账：

| 实体 | 形式 |
|---|---|
| 业务原子 | `BL-<DOMAIN>-[0-9]{3,}` |
| 需求基线 | `REQ-[0-9]{3,}` |
| 决策 | `DEC-[0-9]{3,}` |
| 架构 | `ARCH-[0-9]{3,}` |
| 研究 | `RES-[0-9]{3,}` |
| 对齐 | `ALIGN-...` |
| 复盘 | `RETRO-...` |
| 蒸馏 | `DIST-...` |
| 目标/任务/运行 | `GOAL-`/`TASK-`/`RUN-` |
| 证据/复核 | 大写短横线标识，全局唯一 |

## 4. 长文档边界与版本引用（BL-FRAMELAND-008）

1. 长正文（需求书、架构说明、研究、复核报告、验收记录）只存在于 `.project-log/docs/**`，由 Git 管理。
2. 结构化存储只保存 `doc_ref`：`{"path": ".project-log/docs/x.md", "sha256": "<hex>"}`。
3. 记录或证据引用文档时，写入当时的内容哈希。
4. 文档内容变化后，引用它的证据按记录哈希精确失效（复用 `covered_bytes_changed` 语义），
   而不是按路径交集失效。
5. 校验器在任意深度拒绝 `records.payload` 中长度超过 4096 字节的字符串，
   与写入路径同规则，以阻止把正文复制成第二事实源（含直接落库的篡改）。

## 5. 命令面

### 5.1 命令信封

沿用现有信封：`{schema_version, command_id, expected_revision, action, payload}`，
`command_id` 幂等，`expected_revision` 乐观并发，冲突返回明确错误而非隐式修复。

### 5.2 动作集合

| 类别 | 动作 |
|---|---|
| 现有 | `goal.create`、`task.create`、`task.update`、`task.begin`、`task.wait`、`task.resume`、`task.handoff`、`task.finish`、`task.cancel` |
| 新增 | `goal.update`、`goal.complete`、`record.create`、`record.update`、`record.link`、`evidence.record`、`evidence.invalidate`、`review.record` |

> 修订（TASK-047 后）：`task.update` 只允许写入 `implementer`/`owner` 归属字段。
> 高风险任务在缺少实现者时门禁 fail-closed，而迁移来的任务可能没有 `owner`，
> 因此需要一个受约束的归属写入动作；`risk`、`verification` 等会影响门禁的字段不可经此修改。
> 同理新增 `goal.update`，只允许替换 `success_conditions`/`required_evidence`：
> 没有它，成功条件只能停留在创建时的 `pending`，任何目标都无法完成；
> `risk_level` 等门禁相关字段不可经此修改，且 `passed` 条件仍必须引用有效证据。

### 5.3 门禁（BL-FRAMELAND-004）

- `task.finish` 前置：该任务至少有 1 条 `status=valid` 且 `covers.tasks` 含该任务的证据；
  否则拒绝并返回缺少的证据。
- 任务 `extensions.risk == "high"` 或 `verification.level >= 3` 时，`task.finish` 还要求存在
  一条 `reviews` 记录，`task_id` 相同、`verdict == "go"`、`reviewer` 与实现者不同。
- `goal.complete` 前置：所有 `success_conditions[].status == "passed"` 且引用的证据都是 `valid`；
  `required_evidence[]` 每项都有匹配且有效的证据。未满足时返回逐条原因。
- 证据覆盖的产物字节变化后，证据转为 `stale`；已 `stale` 的证据不再支撑完成判定。
- `not-applicable` 的检查项必须在 `extensions.verification.limitations` 或
  `success_conditions` 中带显式理由。

## 6. CLI 契约

### 6.1 正式入口

```text
vibe init [--dry-run]
vibe status
vibe validate
vibe task begin|update|wait|resume|handoff|finish|cancel
vibe record create|update|link
vibe evidence record|invalidate
vibe review record
vibe gate [--task TASK-ID]
vibe goal update|complete --id GOAL-ID
vibe route ...
vibe context TASK-ID [--budget-bytes N]
vibe render
vibe migrate preview|apply|resume|rollback
vibe exchange status|export|import|finish|abandon
```

- 现有 `vibe state-*` 子命令保留为**别名**，行为必须落到同一实现，不得成为第二套语义。
- `vibe init` 在无 `.project-log` 的目录生成 format 2；已有可识别记录时返回 `skipped` 且不写入。

### 6.2 兼容入口

- `loopctl` 在 format 2 项目下把支持的命令映射到同一存储；不支持的命令返回
  `unsupported_legacy_command` 并提示新入口。
- `loopctl` 在 format 1 项目下**保持现有旧格式写入能力**（迁移窗口），但每次写入输出弃用提示，
  `status`/`validate` 报告 `legacy format: migrate with vibe migrate`。
- 旧格式停止写入属于独立关口，必须由用户在 TASK-044 的阶段说明中确认后才可实施。

### 6.3 退出码与错误

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 校验或门禁未通过 |
| 2 | 用法错误、状态冲突、格式错误、迁移未完成 |

错误必须给出可执行的下一步；`busy_writer` 提示“重试同一命令”；不得把原始
`FileNotFoundError`/`WinError` 直接抛给用户（沿用 TASK-031/TASK-032 的口径）。

## 7. 迁移状态机（BL-FRAMELAND-005）

```text
previewed ──apply──▶ backed-up ──▶ generated ──▶ verified ──▶ switched
    │                   │              │             │            │
    └───────────────────┴──────────────┴─────────────┴────▶ rolled-back
                     任一步失败 ──▶ failed（保留原状与中间产物）
```

1. **preview**：只读。产出实体计数、逐项对账清单、冲突与未映射清单、源目录整树摘要。不写项目。
2. **apply**：需要 `--confirm <preview_hash>`。顺序为
   备份（`rollback_bundle`）→ 生成新格式存储 → 导入实体与证据 → 校验 → 原子切换。
3. **原子切换**：先把状态库放到最终位置，再把旧格式文件整体移动到 `.project-log/legacy/`
   （保留原始字节与相对路径），补齐 `.state/`、`.gitignore`、`exchange/.gitattributes` 布局，
   **最后写 `state-format.json`**——标记是唯一提交点，任一步失败都不得留下“两个事实源”或
   “声称 format 2 却没有状态库”。每一步必须幂等，使中断后 `resume` 可以继续而不是重新开始。
   补充（TASK-045 复核 D-003/D-005 后澄清）：`.project-log/docs/**` 是两种格式共用的长正文位置
   （见第 4 节），迁移**不移动**它；只有旧格式的结构化文件进入 `legacy/`。`rollback` 必须删掉
   迁移自己创建的 `.gitignore` / `exchange/` 布局，但不得删除旧格式原本就有的同名文件。
4. **resume**：日志位于 `.project-log/.migration/journal.json`，记录已完成步骤与产物摘要；
   重跑 `vibe migrate resume` 从最后一个未完成步骤继续，已完成步骤不重复执行。
5. **rollback**：恢复 `legacy/` 到原位并移除标记；若迁移后已有新写入，则先把它们导出到
   `.project-log/legacy/new-writes/` 再回退，**不得丢弃**（AC-FL-011）。
6. **冲突判定**（冻结）：
   - 中止：实体 ID 重复、引用悬空、源文件摘要与 preview 不一致、目标已有 format 2 存储。
   - 不中止：字段无法映射到新模型的历史内容。它们进入 `.project-log/legacy/unmapped/` 并附清单，
     因为真实项目（如 `my_lunwen` 的 39 个任务）普遍带有新模型之外的字段，中止会让迁移无法完成，
     而丢弃会违反“不丢历史”。此条**细化并替代** TASK-040 原 `done_when` 中
     “不可映射内容导致停止切换”的措辞。

## 8. 跨平台与上下文（BL-FRAMELAND-009）

- Windows PowerShell 5.1 与 7、Linux/WSL 上同一命令的语义与退出码一致。
- 已知平台差异（PS7 `-File` 预拆带盘符的等号参数）必须显式记录并给出替代调用方式，不静默吞掉。
- 分支与 worktree 切换后 `context_id` 必须变化；跨上下文写入被拒绝而不是覆盖。
- 快照交换只经 `exchange/` 文本快照，不提交 SQLite 二进制。

## 9. 验收映射

| 原子验收 | 可执行验收方式 |
|---|---|
| AC-FL-001 | 空目录 `vibe init` 生成 format 2 且无需实验开关（TASK-035） |
| AC-FL-002 | 已有 `.project-log` 时重复初始化 skipped 且不覆盖（TASK-035） |
| AC-FL-003 | format 2 项目调用旧写入口被拒且旧文件字节不变（TASK-038） |
| AC-FL-004 | format 2 项目的状态变更只写入新格式存储（TASK-038） |
| AC-FL-005 | 14 类实体与链接可写入、查询并校验引用（TASK-036） |
| AC-FL-006 | 未支持的 kind/action 显式报错，不落自由文本（TASK-036） |
| AC-FL-007 | 缺少绑定证据或复核时拒绝完成并逐条说明（TASK-037） |
| AC-FL-008 | 覆盖产物变化后证据转 `stale` 且任务回到未完成（TASK-037） |
| AC-FL-009 | 未授权迁移时旧格式项目字节不变（TASK-040） |
| AC-FL-010 | 显式迁移无损、可续跑、可回退（TASK-040） |
| AC-FL-011 | 回退保留迁移后的新写入（TASK-040） |
| AC-FL-012 | 旧格式项目仍可只读使用并得到迁移指引（TASK-044） |
| AC-FL-013 | 退役阶段的支持范围与用户关口有记录（TASK-044） |
| AC-FL-014 | 正式入口与兼容入口结果一致且写同一事实源（TASK-038） |
| AC-FL-015 | 规则资产与文档按新入口端到端可用（TASK-042） |
| AC-FL-016 | 长文档变化使引用它的证据失效（TASK-036） |
| AC-FL-017 | 结构化存储中不存在可独立漂移的正文副本（TASK-036） |
| AC-FL-018 | Windows 与 Linux 关键命令语义一致（TASK-043） |
| AC-FL-019 | 分支与 worktree 上下文判定正确、不跨上下文覆盖（TASK-043） |

## 10. 未决与升级

- 旧格式停止写入、停止读取、停止支持三个时间点：各自需要用户确认，TASK-044 负责提出。
- `vibe-coding` 自身 `.project-log` 迁移：TASK-045 通过后单独申请授权（TASK-046）。
- 本轮不引入多主同步、常驻服务或远程后端。
