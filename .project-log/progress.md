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
- 验证：`git diff --check` 通过；提交 `f333be9` 已通过 `127.0.0.1:10808` 推送到 `origin/main`。

## 2026-07-28T12:00:00+08:00 归档 vibe-coding 工程记录

- 目标：将当前工程最新 `.project-log/` 同步到 `My_knowledge_base/工程记录/vibe-coding/.project-log/`。
- 动作：删除归档目标中的旧 `.project-log/`，复制当前版本，并提交推送知识库。
- 状态：已完成。
- 验证：归档目标包含 62 个文件；知识库提交 `99eb7da` 已推送到 `origin/work_record`。

## 2026-07-29 源码讲解 Skill 同步

- 状态：已完成源码 Skill 同步、项目日志更新和本地验证，待提交并推送 `origin/main`。
- 新增：`skills/b-source-code-tutoring/`，包含主 Skill、Codex 展示元数据和源码讲解模板。
- 方法：固定为“具体输入 → 真实运行时间线 → 状态变量生命周期 → 源码逐行实现 → 下游消费/结果回调 → 最后工程概念抽象”。
- 边界：Skill 保持显式触发，不新增主 Agent 自动路由；短术语问答、代码审查和无具体路径的泛化架构概述不触发完整教学流程。
- 评测：新增 `.project-log/evals/source-code-tutoring.yaml`，覆盖正常异步调用链、逐行回调和非触发短问答。
- 验证：包校验通过；项目日志 schema 校验通过；22 个 unittest 通过，1 个历史 0.3.0 迁移测试跳过。
- 下一步：审阅最终差异后提交并推送 `origin/main`。


## 2026-08-01T15:20:00+08:00 ???? MCP ????hooks ??????

- ????????????????
- ???PATH ? `python` ? Conda base ? Python 2.7.14????????????????????? `config.toml` ??????????? hooks ????codegraph MCP ? marketplace?
- ???? `D:\conda\envs\vibe-coding\python.exe`?3.11.15??? `global_installer.py update --access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt`?hooks ???? `C:\Users\12187\.codex\config.toml`?SessionStart/PostToolUse/PreCompact ?? `C:\Users\12187\.codex\vibe-workflow\hooks\*.py`??
- MCP?`codex mcp list` ?? codegraph?document-loader?github?playwright?web-search?context7 ? enabled?codegraph initialize ?????? serverInfo codegraph 1.5.0?
- ???`codex plugin list` ?? `vibe-toolbelt@vibe-global-toolbox` installed, enabled, 0.4.1?
- ???installer verify?validate_project?validate_workflow?loopctl validate ?????pytest `21 passed, 1 skipped, 4 subtests passed`?session_start hook ?????? Loop ???
- ???????????? ACP ????????????? MCP/plugin ???
- ???`INSTALL-003`?

## 2026-08-01T15:30:00+08:00 根因分析：MCP/hooks/插件为何安装后又失效

- 状态：根因已闭环，防复发方案待用户确认，暂不改代码。
- 根因：`cc-switch`（桌面模型接管工具）在启动/异常恢复/热切换时整写 `C:\Users\12187\.codex\config.toml`，只保留其管理的模型字段（`model_provider/model/model_catalog_json/[model_providers.custom]`），删除 Vibe 受管的 hooks、MCP、marketplace、plugins 段。
- 证据链：
  - 备份时间线：7/27 07:58 首次抹除（636 字节旧格式，hooks 已丢、保留 projects/windows）；7/27 22:28 更新后配置完整 2027 字节（含 hooks+codegraph MCP+marketplace）；7/28 20:37、7/29 20:55、8/1 08:33 三次被裁为 394 字节，均与 cc-switch 日志“重新接管”时间戳吻合。
  - 394 字节配置含 `model_catalog_json = "cc-switch-model-catalog.json"`、`experimental_bearer_token = "PROXY_MANAGED"`，为 cc-switch 接管产物。
  - cc-switch 数据库 `proxy_live_backup` 表：codex 的 original_config 仅含模型字段，证明其“备份”不保留 Vibe 受管段。
  - 安装器 `backup()` 在写入前执行，安装备份反映的正是被裁后的状态，不能用来还原完整配置。
- 为什么装了又失效：安装器只在运行时恢复配置；cc-switch 开机自启（launchOnStartup + silentStartup），每次重启/接管即再次覆盖，Vibe 无守护。
- 防复发候选（待用户选择）：A) 关闭 cc-switch 对 Codex 的接管/自启；B) 安装器增加配置自愈/校验（功能改动）；C) cc-switch 若支持合并保留其他段则开启。
- 证据：`ROOTCAUSE-001`；决策：`DEC-002`。
- 下一步：用户确认防复发方案后实施，并将结论归档到知识库。

## 2026-08-01T15:10:00+08:00 实测复现：cc-switch 热切换再次删除 Vibe 配置段并已恢复

- 状态：实测复现根因，配置已通过安装器恢复，防复发方案仍待用户确认。
- 复现：用户用 cc-switch 热切换模型（15:05:16/15:05:27 两次热切换），`config.toml` 被整写为 497 字节，mtime 15:05:27 与日志吻合；hooks、marketplace、plugins 段丢失。
- 细节：本次 cc-switch 保留了 `[mcp_servers]` 段（cc-switch 自身管理 MCP），因此 `codex mcp list` 中 codegraph 仍 enabled；但 `codex plugin list` 中 vibe-toolbelt 与 vibe-global-toolbox 已消失。
- 恢复：`global_installer.py update --access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt` 重新写入完整配置（1783 字节，hooks+codegraph MCP+marketplace+vibe-toolbelt），模型配置保留；installer verify 通过；备份 `vibe-global-update-20260801-150629-068198`（恢复前 433 字节，同样为被裁状态）。
- 验证：`codex mcp list` 全 enabled（codegraph/document-loader/github/playwright/web-search/context7）；`codex plugin list` 显示 vibe-toolbelt@vibe-global-toolbox installed, enabled 0.4.1。
- 证据：`REPRO-001`。
- 下一步：用户确认防复发方案（A 关闭 cc-switch 接管/自启；B 安装器自愈守护；C 合并写）后实施，避免再次手动恢复。

## 2026-08-01T15:20:00+08:00 实测：cc-switch“应用通用配置”可透传 Vibe 块，但与安装器不兼容

- 状态：方案 C（通用配置托管）功能层面验证可行，但发现与安装器 update 的兼容缺陷，需安装器增强后才能真正落地。
- 实验：用户把带 `VIBE-CODEX-GLOBAL:CONFIG:BEGIN/END` 标记的完整 Vibe 块写入 cc-switch 通用配置（`settings.common_config_codex`），热切换模型后：
  - `config.toml`（1815 字节）仍含 `[[hooks.*]]`、`[marketplaces.vibe-global-toolbox]`、`[plugins."vibe-toolbelt@vibe-global-toolbox"]`，通用配置两行（model_reasoning_effort/disable_response_storage）也透传成功。
  - `codex mcp list` 全 enabled；`codex plugin list` 显示 vibe-toolbelt installed/enabled 0.4.1。
- 兼容缺陷（离线模拟安装器剥离逻辑确认）：
  - cc-switch 序列化时把 `[model_providers]`、`[mcp_servers.codegraph]`、`[model_providers.custom]` 插入 Vibe 标记块内部，安装器 `strip_config_block` 剥离标记块时会误删这些段。
  - cc-switch 序列化丢失了行尾注释 `# VIBE-CODEX-GLOBAL:CONFIG:END`，安装器会抛 `unterminated managed block`，update 无法运行。
- 影响：Codex 运行不受影响（标记只是安装器专用）；但此后不能再跑 `global_installer.py update`，否则会报错。
- 结论：通用配置托管方向可行（覆盖热切换与启动接管两个触发点），但需要安装器增强：容忍缺失 END、剥离标记块时抽出保留混入的 model_providers/mcp_servers 段。这属于方案 B 的功能改动，待用户确认后实施。
- 证据：`COMMONCFG-001`；决策：`DEC-002`（更新）。
- 下一步：用户确认是否实施安装器增强；临时状态下避免运行安装器 update。

## 2026-08-01T15:28:00+08:00 安装器兼容增强已实施并端到端验证

- 状态：已完成实现与验证。方案 C（cc-switch 通用配置托管）+ 安装器兼容增强落地。
- 改动（`scripts/global_installer.py`）：
  - 新增 `config_block_bounds`：BEGIN 存在但 END 缺失时把块范围扩展到 EOF，不再抛 `unterminated managed block`。
  - 新增 `_sections_in_block`/`preserved_provider_sections`：剥离标记块前抽出混入的 `[model_providers]`/`[model_providers.*]` 表；`preserved_mcp_sections` 复用同一逻辑。
  - `install_config`/`remove_config`：剥离后把保留段合并回配置，避免误删用户模型供应商与 MCP 配置。
- 测试（`tests/test_installer.py`）：新增 `test_update_repairs_cc_switch_rewritten_config` 与 `test_uninstall_preserves_cc_switch_provider_config`。
- 验证：pytest `23 passed, 1 skipped, 4 subtests passed`；validate_package 通过；compileall 通过；真实环境 `update --access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt` 成功修复 cc-switch 重写后的 `config.toml`（1848 字节：model_providers 保留、END 恢复、hooks/marketplace/vibe-toolbelt 完整），`codex mcp list` 全 enabled，vibe-toolbelt 0.4.1 正常。
- 证据：`COMPATFIX-001`；决策：`DEC-002` 更新为 approved。
- 下一步：用户可将 cc-switch 通用配置（模板 `cc-switch-common-config-codex.txt`）保持现状；如需提交代码，先 review diff 后 commit/push。
