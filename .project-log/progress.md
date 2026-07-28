# Progress

## 2026-07-27T11:48:34+08:00 可选 MCP catalog 与 CodeGraph

- 状态：已完成实现、验证和全局安装。
- Vibe Coding：版本 `0.4.1`；新增 `runtime/mcp/optional-mcps.json`，新安装默认不启用可选 MCP。
- 安装器：支持重复 `--mcp NAME`；保留 `--without-mcp` 兼容参数；状态记录 `optional_mcps` 和所有权；验证/卸载支持 catalog。
- 当前选择：`codegraph`。
- Codex：`codex mcp list` 显示 `codegraph` enabled，命令为 `/home/tbl/.local/bin/codegraph serve --mcp`。
- CodeGraph：LeRobot 索引 `804 files / 17,512 nodes / 46,134 edges`，状态 up to date。
- 验证：包校验通过；21 个 unittest（1 个历史归档测试 skipped）；release/plugin validation 通过；全局 verify 通过。
- 下一步：重启 Codex 或 Zed ACP Thread，使当前 MCP 在新会话工具列表中加载。

## 2026-07-27T21:54:40+08:00 Windows 测试夹具兼容性修复

- 状态：已完成实现和验证。
- 修复：测试中的 Conda、Codex、CodeGraph 模拟命令在 Windows 使用 `.cmd` 包装器；Hook 测试同时校验 Unix `command` 和 Windows `commandWindows`；TOML 测试路径使用合法的 POSIX 表示。
- 验证：20 个 unittest 通过，1 个历史归档测试 skipped；包校验、插件校验和 Python 编译检查通过。
- 发布：`dist/vibe-coding-codex-global-core-0.4.1.zip` 已重新生成并通过校验。
- 证据：`MCP-006`、`MCP-007`。


## 2026-07-27T22:15:00+08:00 Windows ??????

- ???????????? smoke test?
- ????? Vibe Coding Core ? `0.4.0` ??? `0.4.1`?????? `C:\Users\12187\.codex\backups\vibe-global-update-20260727-221129-704101`?
- Python?????? Conda ?? `vibe-coding`????? `D:\conda\envs\vibe-coding\python.exe`???? pytest ???????? `C:\Users\12187\.codex\vibe-python`?
- ????????? `keep-existing`?Hooks ??????????????? MCP?
- ?????????Project Log?Workflow?Loop ???????pytest `20 passed, 1 skipped`?????????????????????? smoke test ?????
- ????? Conda `4.4.10` ??? `conda run`????????????? Python ????????????Codex `0.145.0` ? PATH/npm ????????????
- ???`INSTALL-001`?

## 2026-07-27T22:30:32+08:00 可选 MCP 与插件安装完成

- 状态：已完成安装、配置、验证和 Windows 回归修复。
- 安装：通过 `global_installer.py update --access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt` 同步全局配置；保留备份 `C:\Users\12187\.codex\backups\vibe-global-update-20260727-222855-802325`。
- MCP：`codegraph` enabled，stdio 命令为 `npx --yes @colbymchenry/codegraph serve --mcp`。
- 插件：`vibe-toolbelt@vibe-global-toolbox` installed, enabled，版本 `0.4.1`。
- 修复：Windows 下安装器和回归测试统一使用 `shutil.which("codex")` 返回的可执行路径，避免 `.cmd` 包装器导致 `WinError 2`。
- 验证：installer verify、package/project/workflow/Loop validate 全部通过；pytest `21 passed, 1 skipped, 4 subtests passed`；Codex MCP 和插件列表冒烟检查通过。
- 边界：尚未在当前已运行 ACP 线程内直接调用 MCP/plugin 工具；需重启 Codex 或 Zed ACP Thread 使新能力加载。

## 2026-07-28T11:00:00+08:00 project-log-archive 路由补齐

- 状态：已完成源提示路由更新，待提交并推送。
- 变更：在 `prompts/vibe-global-agent.md` 增加 `a-project-log-archive` 路由；在 `docs/skill-routing.md` 增加工程日志归档映射。
- 验证：全局 `/home/tbl/.codex/AGENTS.md` 已包含同名路由；仓库中的 Skill 目录已存在。
- 下一步：运行 diff 检查和脚本编译检查后提交并 push `main`。

## 2026-07-28T11:30:00+08:00 Git push 代理规则

- 变更：全局 Agent 规则和 Vibe Coding 源提示增加统一规则：`git push` 失败时使用 `127.0.0.1:10808` HTTP/HTTPS 代理重试。
- 验证：待执行 diff 检查并推送。
