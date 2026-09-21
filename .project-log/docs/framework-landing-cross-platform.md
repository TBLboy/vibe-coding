# format 2 落地跨平台验收（TASK-043）

> 状态：Linux 已完成；Windows PowerShell 5.1/7 未在本机环境执行。

## 已执行环境

- Host: Ubuntu 22.04 内核，Python 3.11.15（`vibe-python`）。
- 测试命令：`python -m unittest discover -s tests -p 'test_*.py' -q`。
- 结果：107 项通过，1 项跳过（跳过项为环境依赖）。

## Linux 已覆盖

| 检查 | 结果 |
|---|---|
| `runtime/vibe.sh` 通过用户级 `vibe-python` 转发 `init` | passed |
| Git 分支切换后 `context_id` 隔离，缺失状态库明确报 `missing_store` | passed |
| 切回原分支后恢复同一状态库 | passed |
| `runtime/vibe.ps1` 存在并转发到同一 `scripts/vibe.py` | static-pass |
| format 2 的 task/record/evidence/review/gate/migrate 回归 | passed |

## Windows 未执行项

当前执行环境没有 Windows、PowerShell 5.1 或 PowerShell 7，也没有可用的跨系统执行器。因此以下项目仍是未验证项：

- PowerShell 5.1 与 7 的实际启动、参数转义和退出码；
- Windows 路径、盘符和 worktree 下的状态库定位；
- Windows 上迁移的原子替换与回退。

这些限制不允许被解释为 Windows 已通过。TASK-044 可以继续准备发布材料，但发布前必须补跑 Windows 矩阵。
