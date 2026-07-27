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
