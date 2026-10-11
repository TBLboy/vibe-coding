# 发布说明

## 0.6.0 —— 0.6 ledger architecture：Git 账本为唯一事实源

### 一句话

结构化工程日志改为**账本优先**：每条命令先追加到 Git 跟踪的账本并 `fsync`，本机 SQLite
降级为可重建投影；一份 Project Log 覆盖一个项目的所有分支，换机时用知识库搬运账本。

### 写入路径

- `Store.apply` 现在是 ledger-first：账本追加是唯一 commit point，SQLite 随后更新。
  读取 `expected_revision`、追平投影、提交命令处于同一个 `BEGIN IMMEDIATE` 事务内，
  因此在锁外观测到旧 revision 的写入者会被判 `stale_revision`，不会覆盖先提交的写入者。
- 进程在账本 `fsync` 与 SQLite commit 之间崩溃时，读取命令（`vibe status`/`context`/`gate` 等）
  会先从账本追平投影再作答，不再静默返回崩溃前的旧 revision。
- 同一 `command_id` 重放是幂等的：崩溃后重试同一信封会返回账本里已持久化的 receipt，
  并在返回前先把落后的账本补回；不会重复记账。
- 追平方向由命令 id 序列判定，不用账本 tip 的 `origin_revision` 冒充账本位置，
  跨上下文 revision 相同的账本不会被误判为 in-sync。
- 命令 id 相同不代表内容相同：共享命令仍逐字节校验，账本在同 id 下改写历史会
  以 `history_rewritten` fail closed；投影与账本重放不一致时（含 id 完全一致的情况）
  由 `state-attach` 整体重建，不会把伪造的投影当成 in-sync。
- 读取路径同样按身份校验：`vibe status` 遇到同 id 改写或双向不包含的账本会 fail closed，
  不再打印正常状态；派生的 command/event 行被篡改时 `state-attach` 会从账本整体重建。
- 账本领先时只回放缺失尾部、不重写历史；SQLite 领先账本（例如账本被回滚或从未导出）时
  重新导出，且共享命令必须逐字节一致，否则 fail closed 报 `ledger_diverged`。
- `state-attach` 双向追平：干净克隆从账本重建，账本为空/落后的工作目录从 SQLite 重新导出。
- `portability-status` 把本地一致性与远端耐久性分开报告：本地新鲜度按命令身份判定（同 revision
  的异源账本不会被判为一致），远端耐久性由知识库归档配置决定，未配置时报告
  `archive_not_configured`，而不是继续给出 `portable=true`。

### 项目级日志

- 状态 identity 改为项目级：`context_id` 只由 `{root, git_dir}` 计算，不再把分支名算进去。
  同一 worktree 切换分支后日志仍然可见，不再需要 `state-attach`/`state-import` 找回。
- 这是对 format 2“每个分支独立状态”契约的显式变更，记录为 DEC-013。

### 归档与换机

- `a-project-log-archive` 改为合并：按 `command_id` 校验知识库账本是本地账本的前缀，
  只追加新增命令，显式排除 `.state/`、`.git`、`.migration/`、`legacy/new-writes/`，
  并在 `project_id` 不一致时拒绝覆盖；重复归档幂等。
- 新增 `a-project-log-align`：从知识库把归档账本与本地账本做并集（本地命令一条不丢），
  重新封好哈希链，只补齐缺失的 `docs/`，然后自动执行 `state-attach` 与 `validate`。

### 兼容性

- 账本目录 `.project-log/ledger/v1/ledger.jsonl` 与 `state-format.json` 结构不变；
  旧的分支级 SQLite 只需一次 `state-attach` 即可从账本重建为项目级。
- 非 Git 的 work 目录行为不变，identity 仍为 `branch: "local"`。
- **Project Log format 2 是唯一受支持的格式。** format 1 已完成退役：`SUPPORTED_FORMATS`
  只含 `2`，`vibe`/Hooks 不再解析或写入 format 1；旧模板、旧解析分支、迁移工具
  （`state_migrate`）、兼容入口（`loopctl`/`loop_state`）与三个分步退役关口一并移除。
- format 1 的历史文件完整保留、不被清理：`.project-log/legacy/`（含 `legacy/unmapped/`）
  与 `.project-log/docs/archive/legacy-format1/`。这些存档只供人工查阅，不参与状态库、
  校验或门禁。退役过程不改写任何持久化值（`store_schema` 仍为 3、各 `schema_version` 仍为 1），
  也不追溯改写历史。

## 0.5.0 —— format 2 转正为新项目默认

> **已在 0.6.0 取代**：format 1 已退役，`loopctl`、迁移工具与三个退役关口均已移除。
> 本节关于 format 1 只读兼容、显式迁移与退役关口的描述仅作历史记录，不再反映当前行为。

### 一句话

新项目默认使用事务性 project-log format 2；format 1 进入只读兼容 + 显式迁移窗口，
退役分三步，每一步都必须由用户确认。

### 默认行为变化

- `vibe init`（等价于旧的 `vibe state-init`）在空目录生成 **format 2**，不再需要
  `--experimental`；重复初始化在已有 `.project-log` 时返回 `skipped` 且不覆盖。
- 正式命令面统一到 `vibe`：`task`、`record`、`evidence`、`review`、`gate`、`route`、
  `context`、`exchange`、`migrate`、`version`。
- `loopctl` 保留为兼容入口：format 2 项目下支持的命令映射到同一状态库，不支持的写命令
  返回 `unsupported_legacy_command` 并提示新入口，不产生第二事实源。
- 任务完成需要覆盖该任务的 `valid` 证据；高风险任务还需要独立 reviewer 的 `go` 复核；
  目标完成按成功条件与必需证据裁决。

### format 1 只读兼容与迁移

- format 1 项目在新安装下仍可被读取：`vibe status`、`loopctl status`、`loopctl validate`
  会输出 `legacy format: migrate with vibe migrate` 指引。
- format 1 写入在迁移窗口内仍然可用，但每次写入都会在 stderr 输出弃用提示。
- 迁移工具：`vibe migrate preview` → `vibe migrate apply --confirm <preview_hash>` →
  `vibe migrate resume` / `vibe migrate rollback`。迁移前先备份，迁移日志写入
  `.project-log/.migration/journal.json`，无法映射的历史进入 `.project-log/legacy/unmapped/`
  而不是被丢弃。
- 未获显式授权时，迁移工具不会改写 format 1 项目的字节。
- 迁移不会把旧的“已完成”直接当作 format 2 的完成：旧任务状态保留在
  `extensions.legacy_status`，但只有当覆盖该任务的证据在当前字节下仍然有效、且高风险任务
  有独立 `go` 复核时，才会重建为 `implemented-unverified`；否则任务回到 `ready`，并把
  “completion gate could not be reproduced” 与逐条原因写入
  `.project-log/legacy/unmapped/unmapped.json`。这是 fail-closed 行为，不是数据丢失：
  旧状态、旧证据与旧字段都可在 `legacy/` 中按原样找到。
- 由此，迁移一个真实项目可能让“证据已随源码变化失效”的历史任务重新变为 `ready`，
  需要按当前字节补证据后重新完成。
- 迁移自带的文件搬移（`.project-log/**` → `.project-log/legacy/**`）**不会**让证据失效：
  记录的路径保持不变，适用性检查在旧路径不存在时会到 `legacy/<同路径>` 按哈希解析，
  只有哈希仍然匹配才算有效。旧路径只要还存在就以旧路径为准，因此真实的修改或删除
  不会被未改动的 `legacy/` 副本掩盖；被重定位的引用会记入迁移 journal 的
  `relocated_references`。

### format 1 退役阶段与用户关口

三个阶段都**不会**由代理自行执行；每一阶段都需要用户单独确认后才可实施：

| 阶段 | 支持范围变化 | 关口 |
|---|---|---|
| `stop-writing` | `loopctl`/`vibe` 不再接受 format 1 写入；只读查询与迁移仍可用 | 用户确认 |
| `stop-reading` | `status`/`validate`/`restore` 不再解析 format 1；迁移工具仍可离线运行 | 用户确认 |
| `stop-support` | 移除迁移工具、旧模板与兼容代码 | 用户确认 |

当前三个阶段的 `status` 都是 `pending`。机器可读副本见
`runtime/scripts/framework_info.py` 的 `RETIREMENT_STAGES`，可用 `vibe version` 查看。

### 迁移授权边界

- 真实项目的迁移由该项目自己决定并单独授权，不随框架升级自动执行。
- `vibe-coding` 仓库自身的 `.project-log` 迁移是独立授权项。用户已于 2026-09-21 显式授权
  （DEC-010），该仓库自身已在独立复核通过、预览零冲突、备份与回退演练完成后迁移到 format 2。
- 安装、升级、卸载都不会改写任何项目的 `.project-log/`。

### 版本与校验

- 版本单一来源：`runtime/scripts/framework_info.py` 的 `VERSION`；安装器与发布打包脚本
  都从该文件读取，`vibe version` 与 `--version` 输出同一值。
- 校验入口：`python runtime/scripts/validate_package.py --root .`、
  `python runtime/scripts/validate_project.py --root .`、
  `python runtime/scripts/loopctl.py --root . --json validate`。
- 已知限制：本版本在 Linux/WSL 上完成回归；Windows PowerShell 5.1/7 的实机矩阵仍标记为
  `implemented-unverified`，不得解释为已通过。

### 升级方式

```bash
./update.sh          # Linux/macOS
.\update.ps1         # Windows
```

升级保留用户本地修改，冲突在写入前停止并报告。旧安装状态（0.3.0 起的整树 hash 记录）会在
文件未被本地修改时自动迁移为逐文件状态。
