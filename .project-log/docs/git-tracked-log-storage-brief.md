# 背景简报：让工程日志全部进入 Git，同时保留结构化快速记录

> 用途：提交给外部模型或工程师做方案评估。本文只陈述已核实的事实，未核实项显式标注。

## 一、目标与确切问题

### 需求

1. **G1**：所有工程日志都能被 Git 跟踪。换一台电脑 `git clone` 之后，工程日志与项目进度必须完整恢复，不能只存在于原机器上。
2. **G2**：保留现有"结构化快速记录"的写入模式——Agent 通过一条 CLI 命令登记任务、证据、决策、复核，框架自动维护状态机、完成门禁、证据版本绑定与失效传播。这个体验不能退化。

### 需要回答的问题

- **Q1**：满足 G1 + G2 的存储架构应该是什么？事实源放在哪里？
- **Q2**：如果把追加式文本账本作为 Git 中的事实源，并发与合并语义怎么定义？
- **Q3**：把 SQLite 降级为"可重建缓存"是否可行、边界在哪？
- **Q4**：有没有比下述 D 方案更成熟的既有做法？（事件溯源、append-only log over Git、CRDT、Git 友好的数据库格式等）

## 二、系统与项目背景

### 是什么

一个自研的 Agent 工作流框架 **Vibe Coding**（版本 `0.5.0`，仓库 `https://github.com/TBLboy/vibe-coding.git`）。它给 Codex 这类编码 Agent 提供一条可追溯的生命周期：

```text
业务澄清 -> 需求基线 -> 方案研究 -> 架构决策 -> 任务拆解
-> 工程说明 -> 实现 -> 验证 -> 对齐 -> 复盘 -> 沉淀
```

所有过程写入项目根目录的 `.project-log/`。

### 关键机制

- Agent 通过 `vibe` CLI 写状态（`task begin/finish`、`evidence record`、`record create`、`review record`、`gate` 等）。
- 完成门禁：`task.finish` 要求至少一条 `valid` 且覆盖该任务的证据；高风险任务还要求独立 `go` 复核。
- 证据有版本绑定：它覆盖的文件字节变化后，证据自动转 `stale`，旧证据不删除。
- 状态分两代格式。**format 1（旧）**：一堆 YAML/JSONL 文件，放在 `.project-log/` 下并被 Git 跟踪。**format 2（当前默认）**：本机 SQLite。

## 三、期望行为 vs 实际行为

### 期望

换电脑 clone 仓库后，以下内容应完整存在：项目目标、47 个任务、10 条决策、3 条对齐记录、98 条证据、3 条复核、189 条命令账本，以及当前进度与精确下一步。

### 实际

上述内容**全部只存在于原机器**的 SQLite 里：

```text
.git/vibe-state/<project_id>/<context_id>/state.sqlite3      (995 KB)
.git/vibe-state/<project_id>/<context_id>/generated/views/   (37 个 revision 目录)
```

`.git` 是 Git 自己的管理目录，**永远不会被 commit、push 或 clone**。clone 下来能拿到的只有：

- `.project-log/docs/*.md`：13 个人写的长文档
- `.project-log/legacy/`：65 个文件、1.7 MB，format 1 时代的历史存档

### 核心矛盾

format 1 时代日志是 YAML 文件、被 Git 跟踪；迁移到 format 2 后，事实源搬进了本机 SQLite，**日志从"随仓库走"退化成了"只在本机"**。这是本次要修复的架构回退。

## 四、复现与确切证据

### 跟踪状态实测

```text
$ git ls-files | grep -c vibe-state
0

$ git check-ignore -q <path>   # 逐路径探针
.project-log/docs/x.md          -> 可跟踪
.project-log/exchange/x.json    -> 可跟踪
.project-log/legacy/x           -> 可跟踪
.project-log/state-format.json  -> 可跟踪
.project-log/.state/x           -> IGNORED
.project-log/.migration/x       -> IGNORED
```

`.project-log/.gitignore` 内容为 `.state/`、`.migration/`、`legacy/new-writes/`。

### SQLite 内容实测（12 张表）

| 表 | 行数 | 内容 |
|---|---|---|
| `goals` | 1 | 项目目标（业务完成契约） |
| `tasks` | 47 | 任务：状态、`done_when`、plan、关联业务原子与决策、风险等级、授权级别 |
| `runs` | 9 | 任务执行轮次 |
| `blockers` | 0 | 阻塞：等待类型、恢复条件、关联问题 |
| `records` | 13 | 决策 10 条 + 对齐 3 条，正文内联在 payload |
| `record_links` | 0 | 记录间引用关系（depends-on / supersedes / verifies 等） |
| `evidence` | 98 | 状态、覆盖范围（文件/需求/任务）、版本绑定、失效原因 |
| `reviews` | 3 | 独立复核结论 |
| `commands` | 189 | 完整命令账本 |
| `events` | 189 | 事件索引 |
| `exchange` | 1 | 快照交换簿记 |
| `metadata` | 1 | 项目 ID、上下文 ID、local_revision |

证据状态分布：49 `valid`、42 `stale`、4 `failed`、3 `candidate`。

### 跨副本交换现状

```text
$ vibe exchange status
exported_local_revision: 0
local_revision: 189
unexported_commands: 189
```

`.project-log/exchange/` 目前只有一个 `.gitattributes`，**从迁移至今一次都没有导出过**。

### 框架自身的文档声明

- `docs/USAGE.md`："Git 项目数据库位于该 worktree 的 Git 管理目录下，按项目 ID 和分支上下文隔离；**不会把 SQLite 文件加入 Git**。"
- `docs/USAGE.md`："长文档正文只放在 `.project-log/docs/**`，结构化记录只保存 `doc_ref`（路径与内容哈希）。"
- `runtime/scripts/state_store.py:21` 源码注释：`Long-form text belongs in Git; a record payload only carries state and references.`
- `docs/USAGE.md`（关于显式快照交换）："跨副本同步只在显式执行时发生……快照对象写入 `.project-log/exchange/`，随 Git 提交分发。"

### 一个与文档不一致的实测

框架声称结构化记录只保存 `doc_ref`，但本项目 13 条 record **没有一条带 `doc_ref`**，决策正文是内联在 payload 里的（单条上限 16384 字节）。`docs/` 下的文件仅通过 evidence 的 `covers.files` 关联，实测只有 4 处引用。

## 五、关键架构事实（评估方案时最需要知道的）

### 框架内部已经是事件溯源架构

- `commands` 表是追加式账本，每行字段：
  `command_id / local_sequence / origin_kind / origin_context_id / origin_revision / action / request_json / request_hash / receipt_json / created_at`
- `runtime/scripts/state_store.py` 中的 `_verify_ledger()` 会**逐条重放整个账本**，重建 goals / tasks / runs / records / record_links / evidence / reviews，再与实体表比对。
- 也就是说，不变量"**实体表 == replay(账本)**"框架已经在维护。SQLite 的实体表本来就是投影，不是事实源。

### 现有的跨副本机制及其局限

`vibe exchange export` 会把完整状态写入工作区，可被 Git 跟踪：

```text
.project-log/exchange/current.json                      # 指针
.project-log/exchange/objects/<sha>.payload.json        # 完整状态包
.project-log/exchange/objects/<snapshot_id>.manifest.json
```

但 `export_bundle()` 返回的字段里**包含 `ledger`，即全部命令**。所以每次导出都是把整段历史重写一遍，N 次导出约等于 N × 全量历史。

导入侧是硬校验、不做自动合并，以下情况直接拒绝：

- `snapshot_diverged`：快照不是从本机记录的共同基线派生
- `unexported_changes`：本机存在尚未发布的命令
- `history_rewritten`：同一 `command_id` 的请求或回执字节不一致

### 派生视图是有界截断的

`current-session.md`、`progress.md`、`handoff.md` 由 `vibe render` 从数据库生成，内容标注为 "Recently updated tasks (bounded)"、"Recent accepted commands (newest first, bounded)"。它们**不是完整日志**，不能作为唯一被跟踪的产物。

## 六、已评估的方案与观察结果

| 方案 | 做法 | 结论 |
|---|---|---|
| **A** | 每次收尾跑 `vibe exchange export` + commit | 零代码改动，但：手动步骤（189 条未导出已证明会被遗忘）；每次导出重写全量历史，增长为 O(N × 历史)；分叉时硬失败需人工仲裁 |
| **B** | 把派生视图落到工作区并跟踪 | 视图有界截断，会丢数据，不能作为完整日志 |
| **C** | 把 SQLite 直接搬进工作区 | 二进制不可 diff/不可合并，两人同时写必冲突；每次写入整文件都变，仓库迅速膨胀；且破坏 `.state/` 目录的格式标记保护机制 |
| **D** | 账本变成 Git 中的追加式文本，SQLite 降级为可重建缓存 | 当前倾向，但尚未实施，也未经外部评审 |

### D 方案的具体形态（待评估）

```text
.project-log/ledger/commands.jsonl      # 追加式账本，每行一条规范化 JSON，Git 跟踪
.git/vibe-state/.../state.sqlite3       # 本地缓存，可删可重建，继续 gitignore
```

要点：

1. 每条命令在同一事务内追加一行到 `commands.jsonl`。
2. `.gitattributes` 设 `commands.jsonl merge=union`，让并发追加自动合并为并集。
3. 排序不依赖 `local_sequence`（那是每副本本地的），用已有的 `origin_context_id` + `origin_revision` 推导全局顺序。`apply_import()` 里已在做这个序列翻译。
4. `vibe state-attach` 语义改为"读 JSONL -> 重放 -> 建缓存"，新克隆直接得到完整历史。
5. `validate` 保持现有的重放校验不变。

## 七、约束与不可破坏项

- 不能削弱现有门禁：`task.finish` 需 `valid` 证据、高风险任务需独立复核。
- 不能丢历史：迁移时对无法映射的旧记录坚持"不中止迁移也不删除历史"，76 条 unmapped 被完整保留。
- 需要跨平台：仓库同时提供 `install.sh` 与 `install.ps1`。
- 需要承载存量数据：47 个任务、189 条命令必须无损迁移。
- 写入方是 Agent（通过 CLI 高频写入），不是人类手工编辑。

## 八、未知与请求帮助

1. **D 是否最优？** 有没有更成熟的既有实践（Git 上的 append-only log、事件溯源、CRDT、或 Git 友好的数据库如 Dolt / TerminusDB / SQLite 的文本后端）？
2. **合并策略**：`merge=union` 是否足够？是否应改为 per-replica 分文件（例如 `ledger/<context_id>.jsonl`）以彻底消除行级冲突？
3. **缓存可靠性**：SQLite 作为可重建缓存的边界在哪？重建耗时如何估计？如何证明重建结果与原状态等价（可复用 `_verify_ledger` 的重放）？
4. **并发语义**：两个分支各自 `task.finish` 同一任务时，重放会因引用不一致而拒绝。这是期望行为，还是需要定义确定性仲裁规则？
5. **长期体积**：189 条命令的 request + receipt 实测 285 KB。10 年量级如何？是否需要快照 + 截断（类似 Raft snapshot / log compaction）？
6. **写路径**：应该保持 SQLite 为唯一写路径（同事务内追加文本），还是让文本账本成为唯一写路径、SQLite 纯派生？

## 九、期望的回答形式

针对 Q1–Q4 给出方案对比与推荐，说明每个方案在**可审计性、可迁移性、可 diff 性、仓库体积、并发与合并、实现成本**六个维度的取舍，并明确指出推荐方案的风险与失败模式。
