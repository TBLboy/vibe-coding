# 发布说明

## 0.5.0 —— format 2 转正为新项目默认

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
- `vibe-coding` 仓库自身的 `.project-log` 迁移同样是独立授权项，需在发布评审通过后单独申请。
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
