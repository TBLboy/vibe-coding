# Vibe Coding 术语契约

本文件是**术语的单一事实源**。代码注释、CLI help、文档、测试名、Skill 与 Agent prompt
必须遵循这里的规定；与本文冲突的表述一律以本文为准。

## 为什么需要它

一次外评审确认：真正的问题不是"版本号太多"，而是**同一个词被用来指代两种不同层级的东西** ——
架构代际名 `Format 3` 与持久化字段 `format` 撞名。后果是 Agent 把 `format 2` 误解成某种
存储/布局模式，进而建议把日志放进 Git 仓库，与设计意图正好相反。

结论：**不要减少版本轴，要给每个轴明确的名称与职责。**

## 一、版本轴（彼此正交，不得合并）

| # | 正式名称 | 当前值 | 存放位置 | 职责 | 何时递增 |
|---|---|---|---|---|---|
| 1 | `framework_version` | `0.6.0` | `runtime/scripts/framework_info.py` | **软件发布版本** | 每次发版 |
| 2 | `format`（Project Log format） | `2` | `.project-log/state-format.json` | **Project Log 顶层持久化契约** | 顶层读写契约发生**破坏性**变化时 |
| 3 | `store_schema`（SQLite store schema） | `3` | SQLite `metadata` 表 | **本地投影数据库结构** | 表结构变化时 |
| 4 | `schema_version`（command envelope schema） | `1` | 命令信封 + SQLite | **命令信封结构** | 信封字段变化时 |
| 5 | `schema_version`（ledger event schema） | `1` | `ledger.jsonl` 每行 | **账本事件结构** | 事件字段变化时 |

此外，生成的视图（`generated/`）与快照指针各自的 `schema_version = 1`，同属"具体数据结构的内部版本"。

**为什么不能合并成一个号**：`store_schema` 历史上从 `1` 递增到 `3`，而 `format` 一直是 `2`。
若合并，每次表结构变化都会被迫触发**全量迁移** —— 而使用者感知不到任何变化。版本号必须只表达
它真正负责的兼容边界。

**为什么不用 `v0.x` 表达数据格式**：`framework_version` 是**软件**版本，会频繁变（修 bug、加功能）；
**数据格式**版本只在兼容性破坏时变。两者是不同维度，`v0.x` 不能兼任。

## 二、`format` 的合法值域

- `2` —— 事务性状态库 + Git 账本。**当前唯一合法、唯一支持的取值**。
- `1` —— legacy 文件式日志（`workflow.yaml`、`task-list.yaml` 等）。**已退役**：不再被任何
  命令解析或写入，历史存档只保留在 `.project-log/legacy/` 与
  `.project-log/docs/archive/legacy-format1/`，不参与状态库、校验或门禁。

## 三、命名规则（每个词只用于一个维度）

| 词 | 只允许用于 |
|---|---|
| `format` | 顶层 Project Log 持久化契约（值 2） |
| `schema` / `schema_version` | 某个具体数据结构的内部版本 |
| `layout` | 磁盘目录拓扑（work-folder layout） |
| `archive` / `transport` | 跨机、远端持久化或搬运机制 |
| `architecture` / `generation` | 发布代际或设计方案 |

## 四、禁止事项

1. **禁止裸写 `Format 2` / `Format 3`。**
   必须写成 `Project Log format 2`，或 `SQLite store schema 3` / `ledger event schema 1`。
2. **禁止把架构代际命名为 `Format N`。**
   0.6.0 这一代架构称为 **`0.6 ledger architecture`**（简称 `ledger architecture`），
   它**不是**任何持久化标识。
3. **禁止为了让版本号"看起来一致"而迁移持久化数据。**
   名称可以重构，事实值不因命名而迁移。

## 五、布局与远端（同批确立）

| 概念 | 契约 |
|---|---|
| 唯一受支持布局 | **plain work folder**：工作目录本身不是 Git 仓库，也不位于任何 Git worktree 内；`.project-log` 是普通目录 |
| 允许的子结构 | 工作目录下可以有多个独立 Git 仓库（`repo-a/`、`repo-b/`） |
| Git-root 布局 | **拒绝**（fail closed），错误信息直接声明期望布局 |
| 远端耐久性 | 由知识库归档提供；本地一致性与远端耐久性是**两个独立报告项** |
| 证据路径 | 相对**工作目录**（work root）解析 |

## 六、错误码（区分布局 / 账本 / 远端）

| code | 含义 |
|---|---|
| `unsupported_work_layout` | 工作目录是 Git worktree 根，或位于某个 Git worktree 内 |
| `archive_not_configured` | 知识库归档不可用 |
| `archive_out_of_sync` | 本地账本新于归档副本 |
| `ledger_projection_mismatch` | SQLite 与账本 head 不一致 |
| `archive_snapshot_inconsistent` | 归档复制期间 head 发生变化 |

布局检测 `detect_layout(root)` 的三个返回值为：

| 返回值 | 含义 | 处理 |
|---|---|---|
| `plain_work_folder` | 工作目录是普通目录，且不在任何 Git worktree 内 | **唯一受支持**，正常读写 |
| `git_worktree_root` | 工作目录本身就是 Git worktree 根 | 拒绝（`unsupported_work_layout`） |
| `nested_in_git_worktree` | 工作目录位于某个 Git worktree 内 | 拒绝（`unsupported_work_layout`） |
