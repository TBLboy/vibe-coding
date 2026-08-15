# Current Session

## 2026-08-15 充实 docs/USAGE.md 用户使用指南（TASK-008）

- 用户确认目标文件为 `docs/USAGE.md`，要求把简略文档写得更丰满。
- 已将文档扩展为完整用户手册：增加全局/项目/对话三层模型、安装准备、项目初始化、端到端工作流、状态模型、失败重试、A/B/C 决策、多客户端、cc-switch/MCP、常用提示、排障、安全边界、恢复和完成标准。
- 验证：包校验、项目日志校验、Loop 校验和 38 个 unittest（1 个跳过）通过；Markdown 代码围栏平衡，文档引用目标存在。
- 记录时间：2026-08-15T12:05:00+08:00。


## 2026-08-15 修复项目日志校验问题（TASK-007）

- 用户要求修复快速检查发现的四个问题：DEC-003 缺少 `hypothesis/options`、verification/evidence.yaml 与 work-trace/trace.yaml 的反引号导致 YAML 解析失败、以及无目标无下一步的残留 active run。
- 已补全 DEC-003 的假设与备选方案；移除导致 YAML 词法错误的 Markdown 反引号；将残留 run 标记为 `complete` 并写入 run-completed/handoff 事件。
- 记录时间：2026-08-15T19:40:03+08:00。
- 验证：validate_project、loopctl validate、validate_package、38 个 unittest（1 个跳过）和 SessionStart smoke 全部通过；恢复视图显示无 active task，Run status 为 complete。

## 2026-08-15 项目初始化 a-project-init skill

- User asked to optimize the framework and entered business clarification: project initialization should also establish/update root `AGENTS.md`, not just `.project-log`.
- Confirmed decisions: keep the existing `init_project.py` chain untouched; new `a-project-init` skill wraps `.project-log` init + `AGENTS.md` creation; existing `AGENTS.md` content is preserved and general rules are injected once via `VIBE-PROJECT-GENERAL` markers (idempotent); general rules template lives inside the skill as the single source; project-specific rules are extracted from root README/docs or left blank with a hint.
- Implemented: `skills/a-project-init/SKILL.md`, `templates/general-rules.md`, `scripts/init_project_agents.py`, `tests/test_project_init.py`; routing added to `prompts/vibe-global-agent.md`; atoms `BL-PROJECT-INIT-001..004`, clarification, requirements, decision `DEC-004`, task `TASK-006` recorded.
- Verification: `test_project_init.py` 6 passed; `validate_package.py` passed; CLI smoke created `.project-log` (62 files) + `AGENTS.md` and second run was idempotent (both skipped); `validate_project.py` clean for new records, only 4 pre-existing issues remain (DEC-003 missing fields, evidence.yaml/trace.yaml YAML parse).
- Status: implementation complete and verified in source repo; `TASK-006` done, `DEC-004` successful.
- Next step: user decides whether to sync the skill to the installed runtime (`global_installer.py update`) and whether to commit/push.
- Installation (user approved): `global_installer.py update --access-profile keep-existing --skip-doctor` succeeded; `verify` passed; `a-project-init` synced to `~/.codex/skills/a-project-init/` (SKILL.md, templates/general-rules.md, scripts/init_project_agents.py); global AGENTS.md routing includes `a-project-init`; installed-layout smoke passed (first run created `.project-log` + `AGENTS.md`, second run idempotent).
- Remaining: commit and push the source changes when the user confirms.

## 2026-08-15 AI_INSTALL/AI_UPGRADE 文档与安装器一致性核对

- User asked to verify AI-assisted install docs against `scripts/global_installer.py`.
- Verified consistent: package version `0.4.1`; default `--access-profile keep-existing`; core-only default install with `--mcp`/`--without-mcp` and mutual-exclusion error; update preserves previously enabled optional MCPs; preflight runs by default (`--skip-preflight` opt-out, checks codex version/features/doctor); timestamped backup before write; upgrade conflicts abort before any write (`Upgrade conflicts detected before writing`); installation-state.json read/write with legacy migration; `.project-log` never part of global install/uninstall/rollback; three hooks (SessionStart/PostToolUse/PreCompact); install.sh/update.sh bootstrap vibe-python env; requirements.txt (PyYAML, jsonschema).
- Noted: `managed_config_block()` still generates quoted `commandWindows` (Windows Codex 0.147+ hook startup issue), and `AI_INSTALL.md` documents this accurately with manual fix instructions; no doc/code contradiction found.

## 2026-08-15 README 补充代理与 cc-switch 使用说明

- User asked to add two details to `README.md`: proxy requirement (default `127.0.0.1:10808`, adjustable via `HTTP_PROXY`/`HTTPS_PROXY`) and cc-switch common-config usage.
- Added proxy bullet under `## 环境要求`; added `## cc-switch 通用配置` section describing regenerating via `scripts/generate_cc_switch_config.py`, overwriting the `VIBE-CODEX-GLOBAL:CONFIG` TOML segment in cc-switch common config, and not copying generated host-specific paths across machines.
- User then asked to add the same two rules to `AI_INSTALL.md`: added `## 代理要求` (default `127.0.0.1:10808`, `HTTP_PROXY`/`HTTPS_PROXY` adjustment, `--without-mcp` fallback) and appended instruction 14 to the AI prompt block; added `## cc-switch 通用配置` section identical in content to README.
- Check: does `AI_INSTALL.md` document the full "create vibe-coding env -> install with it -> configure env path -> run Vibe features in it" flow? Result: not fully. It only implicitly mentions the wrapper script reusing/creating the env (instruction 4); manual Windows/Linux steps install requirements into the default Python instead. Verified actual behavior in `bootstrap_vibe_python.py` (reuse `vibe-python`, else Conda create `vibe-coding` python=3.11, install PyYAML/jsonschema, write `CODEX_HOME/vibe-python`, run installer with it) and `global_installer.py configured_python()` (Hooks use that interpreter). Recommended adding a "## Vibe Python 环境与安装流程" section; awaiting user confirmation before editing.
- User approved: added `## Vibe Python 环境与安装流程` to `AI_INSTALL.md` (create env -> activate -> install requirements -> wrapper install -> write `vibe-python` -> Hooks bound -> all Vibe features run in env; adapts to existing env / existing vibe-python / no Conda / `VIBE_PYTHON` / `VIBE_CONDA_ENV`). Corrected environment targeting in `AI_INSTALL.md` (recommended-instruction 3, Windows/Linux manual steps, temp-project acceptance) and `AI_UPGRADE.md` (instruction 4, Windows/Linux upgrade steps, `update.sh` env note); changed `python3` to `python` for `generate_cc_switch_config.py` in README and AI_INSTALL.
- Full doc/code consistency check passed: version 0.4.1, proxy guidance, cc-switch flow, Windows Hook adapter description, upgrade guarantees (timestamp backup, installation-state.json, legacy tree->per-file migration, preserved local changes, pre-write conflict abort), conflict semantics, rollback (only vibe-workflow + skills), 8 subagent roles, three hooks only (no Stop Hook). No remaining doc/code contradictions found.

## 2026-08-14 Stop-after-status-update root cause

- User sent "继续" in thread `019fa3c1-74a0-7693-97de-209b5b918788`; the model performed one Hook config/hash check, then returned only a status message and made no follow-up tool call.
- Codex logged a normal `task_complete` immediately after that message. The turn had no ERROR, no Hook failure, and no context-limit trigger.
- Evidence: `sessions\2026\07\27\rollout-2026-07-27T21-26-37-019fa3c1-74a0-7693-97de-209b5b918788.jsonl` records the assistant message at `22:11:18.549Z` and `task_complete` at `22:11:18.554Z`.
- Log evidence: turn `01a0009c-a5be-7ac1-9e6a-676c86f3c15c` had `full_context_window_limit_reached=false`, `token_limit_reached=false`, and `model_needs_follow_up=false`.
- Attribution: primarily model-side premature stop. Codex closes a turn when the model stops emitting tool calls; the Vibe Hooks did not fail during that turn.
- Related context: two stale `Function call output is missing` warnings existed from an earlier aborted turn, but they did not directly cause this stop.
- Status: root cause diagnosed; the original SessionStart Hook investigation remains unfinished.
- Next step: continue that Hook investigation or add a framework guard against status-only completion while a Vibe run is active.

## 2026-08-13 Loop recovery and new-run repair

- User reported that a normal task could stop after a state-restoration response without completing the requested work.
- Root causes fixed in source: SessionStart appended handoff events while rendering context; completed or empty runs were rendered as active work; a nested new directory could inherit an ancestor Project Log; no explicit new-run reset command existed.
- Changes: SessionStart now renders read-only context; PreCompact persists handoff; `loopctl start-run` resets stale run state with a unique run ID; workspace roots take precedence and an ancestor `.project-log` is not adopted by a new directory; global agent protocol explicitly forbids restoration-only completion.
- Verification: 31 unit tests passed (1 historical test skipped); package validation passed; `start-run` and installed Hook smoke tests passed; `global_installer.py verify` passed; installed runtime hashes match source.
- Installation: `global_installer.py update --skip-doctor` synced the repair into `/home/tbl/.codex/vibe-workflow`.
- Known unrelated limitation: `runtime/scripts/validate_project.py --root .` still reports pre-existing malformed historical records in `.project-log/verification/evidence.yaml`, `decisions/decision-log.yaml`, and `work-trace/trace.yaml`; no project-log records were altered as part of this code repair.
- Next step: commit the source repair on `main`.

## 2026-08-02 Push closeout

- User paused the current MCP/Codex terminal investigation after the fixes and validations were completed.
- Closeout scope: record progress, commit the current vibe-coding source changes, and push to origin/main through 127.0.0.1:10808 if required.
- Push evidence: commit `cf2b80b` was pushed successfully to `origin/main` through `127.0.0.1:10808`; final worktree verification is pending.

## 2026-08-05 Windows host config sync

- User requested the cc-switch common config be regenerated for this Windows host and the installed hooks re-synced.
- Regenerated `cc-switch-common-config-codex.txt` with `scripts/generate_cc_switch_config.py` using the configured Vibe Python (`D:\conda\envs\vibe-coding\python.exe`).
- Patched the generator to emit the host header comment so the tracked template stays reproducible from the generator.
- Re-ran `global_installer.py update --access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt --skip-preflight`; verification passed.
- Evidence: TOML parses; installed hook hashes match source; generator output equals the tracked file; hook tests `13 passed`; installer tests `10 passed, 1 skipped`.
- Next step: user decides whether to commit and push the local config regeneration.

## 2026-08-14 Pull, merge, and framework install

- User asked to pull the updated remote code, review it, and install it into the local framework without committing yet.
- Pulled `53d611d fix: prevent stale loop state from ending new tasks` (fast-forward from `b138bc0`).
- Merged local hook resilience/UTF-8 changes with the remote update; resolved conflicts in `pre_compact.py` and `tests/test_loop_core.py`.
- Installed the merged framework with `global_installer.py update`; installer verification passed.
- Evidence: hook tests `21 passed, 4 subtests`; installer tests `10 passed, 1 skipped`; `loopctl validate` passed; installed runtime hashes match source.

## 2026-08-05 SessionStart hook resilience fix

- User still saw `SessionStart hook (failed): hook exited with code 1` after the hook protocol fix.
- Reproduced with a non-ASCII UTF-8 payload: the hook crashed while initializing `.project-log` (PermissionError on Windows), forcing exit code 1.
- Root cause: stdin/stdout decoding used the console codepage instead of UTF-8, and project-state initialization failures were uncaught.
- Fix: hooks read/write UTF-8 streams; SessionStart and PreCompact catch project-state failures, return fallback context, and always exit 0 with valid JSON.
- Validation: non-ASCII payload repro exits 0; hook tests `14 passed, 4 subtests`; installer tests `10 passed, 1 skipped`; `codex exec` smoke returns OK.
- Next step: user restarts the terminal and opens a new session to confirm the hook error is gone.

- Current phase: MCP/hooks/plugin ???????
- Current goal: ?? cc-switch ????? `document-loader` MCP ?????????? Codex ???? Hook ????
- Current task: ??????????????????????
- Confirmed facts: `document-loader` ?? `vibe-toolbelt/.mcp.json`?`@latest` ???????? `1.0.17`??? MCP initialize ??? Codex exec ???
- Changes: ?? `awslabs.document-loader-mcp-server@1.0.17`??? `HTTP_PROXY`/`HTTPS_PROXY=http://127.0.0.1:10808`??? `PostToolUse.async` ? `PreCompact.additionalContextLimit`
- Validation: `pytest tests\test_installer.py -q` -> `10 passed, 1 skipped`?`codex exec --ephemeral --json` -> `OK`, exit `0`?`codex mcp list` ?? enabled
- Blocking items: ?
- Next step: ?????? Codex ??????? MCP ?????????????? commit/push ??

## 2026-08-02 MCP 终端复核

- 已确认安装器和插件缓存更新成功。
- 根因证据：Codex 日志记录 `Failed to read MCP server stderr (uvx): stream did not contain valid UTF-8`；不是 MCP 包未安装。
- 修复：`document-loader` 增加 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`，并保留固定版本 `1.0.17` 与 `127.0.0.1:10808` 代理。
- 验证：直接 MCP initialize、普通 Codex exec、SessionStart Hook 均通过。
- 环境差异：当前进程 `codex` 命中 Zed 注入的 `0.145.0`；用户级 npm 路径有 `0.146.0`。需重启终端后确认实际版本。

## 2026-08-03 宿主机配置动态化

- 用户指出 cc-switch 配置示例错误保留 Windows 路径；当前宿主机为 Ubuntu。
- 已确认仓库残留点为 `cc-switch-common-config-codex.txt`；安装器 `managed_config_block()` 本身已从宿主 `CODEX_HOME` 和 `vibe-python` 动态生成 Hook 路径。
- 新增 `scripts/generate_cc_switch_config.py`，将 cc-switch 配置生成职责从人工复制改为宿主机动态解析。
- 当前生成结果：`/home/tbl/miniforge3/envs/vibe-coding/bin/python3.11`、`/home/tbl/.codex/vibe-workflow/hooks/*`、`/home/tbl/Project/vibe-coding`。
- 验证通过：生成器与 canonical 文件一致、TOML 合法、无 Windows 硬编码、安装器测试 `10 passed, 1 skipped`、包校验通过。
- 精确下一步：提交并推送本次配置动态化改动。

## 2026-08-03 SessionStart Hook 协议修复

- 用户反馈新对话仍提示 `SessionStart hook (failed): hook returned invalid session start JSON output`，但 MCP 正常。
- 复现与代码检查确认：Hook 能正常退出并输出合法 JSON，但使用旧式顶层 `additionalContext`，未声明 `hookSpecificOutput.hookEventName`。
- 已修复 `runtime/hooks/session_start.py` 和 `runtime/hooks/pre_compact.py`，分别返回 `SessionStart`、`PreCompact` 事件专用输出。
- 已更新 `tests/test_loop_core.py`，验证输出结构、事件名和 additionalContext。
- 已安装到 `/home/tbl/.codex/vibe-workflow/hooks/`；源码与已安装文件哈希一致。
- 验证：13 个 Loop/Hook 测试通过；11 个安装器测试中 10 通过、1 跳过；包校验通过；Codex ephemeral 返回 `OK`。
- 精确下一步：用户重新开启一个新对话确认实际 TUI 提示；当前修复尚未提交推送。


## 2026-08-14 SessionStart Hook 根因修复（Codex 0.147.0 命令解析变更）

- 现象：终端启动 Codex 时 `SessionStart hook (failed) / hook exited with code 1`；同一 Hook 脚本直连执行 exit 0。
- 根因：Codex 0.147.0 不再通过 shell 解析 Hook 命令中的引号。原配置 `"D:/conda/.../python.exe" ".../session_start.py"` 的带引号命令行无法启动进程（进程从未运行，连模块加载日志都没有），被 Codex 报告为 exit 1。
- 证据：将命令临时改为 `python.exe -c ...` 后 `hook: SessionStart Completed`；改回无引号路径形式同样 Completed，且 Hook 内部日志显示 Python 进程正常启动、import 与 main 全流程通过。
- 修复：`C:\Users\12187\.codex\config.toml` 三个 Hook（SessionStart/PostToolUse/PreCompact）命令与 commandWindows 全部去掉引号（路径无空格），并清除旧 trusted_hash 以便重新信任。
- 验证：`codex exec --dangerously-bypass-hook-trust` 输出 `hook: SessionStart Completed`；三个 Hook 直连均 exit 0 且输出合法 JSON；已安装 Hook 文件哈希与仓库源码一致；诊断残留文件已清理。
- 注意：当前修复只改本地 config.toml，未改 `D:\Project\vibe-coding` 源码；若重新运行安装器覆盖 config，需再次应用无引号形式（建议后续在框架安装器模板中同步此变更）。


## 2026-08-14 部署文档补充 Windows Hook 适配说明

- 决策：框架运行时源码不动（Linux/macOS 部署不受影响），只在部署文档中写明 Windows 专属适配。
- 改动：
  - `AI_INSTALL.md`：新增 “Windows Hook 命令适配（Codex 0.147.0+）” 章节，说明根因、修改 `commandWindows` 去掉引号的步骤、trusted_hash 处理和验证方法。
  - `AI_UPGRADE.md`：Windows 升级章节补充遇到 Hook 失败时的处理指引，指向 AI_INSTALL.md。
  - `README.md`：Windows 安装命令后加一行指引。
- 验证：`validate_package.py --root .` 输出 `Package validation passed.`。
- 约束遵守：未修改 runtime 脚本/安装器模板/任何框架行为代码；Linux/macOS 安装路径不变。


## 2026-08-15 “回复一句就停止”根因排查（只读诊断，未改代码）

- 现象：dexbot/kitchen_robot_home 会话中，模型输出承诺句（“我先检查这两处来源…”“我再补一次项目日志…”）后回合结束，任务未继续；用户多次遇到。
- 排查路径：`~/.codex/logs_2.sqlite` 会话日志 + `~/.codex/config.toml` + `cc-switch-model-catalog.json`。
- 直接证据：最后一次纯文本完成 `response.completed`：`status=completed`、`model=deepseek-v4-flash`、output 仅 `[reasoning, message]`、无 `function_call`；同窗口无 ERROR/WARN、无 Hook 失败、无 `response.incomplete`。Codex 回合在模型响应无工具调用时正常结束。
- 上下文证据：该线程 `input_tokens=229021`（300k 窗口约 76%），`cached_input_tokens=20`（几乎无缓存）；模型为 cc-switch 代理的 `deepseek-v4-flash`（`127.0.0.1:15721`，wire_api=responses）。
- 结论：根因在模型侧（flash 模型在长上下文下倾向“总结+承诺”并以纯文本正常结束，而非继续调用工具），不是用户消息格式、Hook、Loop 或 Goal 机制问题；kitchen_robot_home 无 `.project-log`，可排除 loopctl 恢复状态导致的提前结束。
- 候选缓解（未执行）：复杂 agentic 任务改用 `deepseek-v4-pro`；长会话及时 /compact 或开新会话；catalog 中该模型 `default_verbosity=low`，可在 instructions_template 中强化“必须调用工具继续直到验收”约束。

## 2026-08-15 “回复一句就停止”缓解措施落地（框架侧）

- 决策（B 级，DEC 记录于本条目）：针对根因（flash 模型以纯文本承诺句正常结束回合、无工具调用），在框架与模型提示两个层面加强约束，不改 Hook/Loop 机制。
- 改动：
  - `prompts/vibe-global-agent.md`：新增「回合执行纪律（防止半途停止）」——任务未完成前每次回复必须以工具调用继续或提出必须由用户决策的问题；禁止以“我将/我先/接下来……”承诺句结束；仅任务完成且有验证证据、明确阻塞或用户要求暂停时才允许纯文本收尾。
  - 本机 `~/.codex/cc-switch-model-catalog.json`：`deepseek-v4-pro` 与 `deepseek-v4-flash` 的 `instructions_template` 追加英文版 `## Turn completion discipline` 同款约束（本机文件，不进仓库；cc-switch 切换 provider 时可能重新生成，届时需重新应用）。
  - `~/.codex/AGENTS.md`：已按安装器逻辑重新同步受管区块，校验嵌入内容与 `prompts/vibe-global-agent.md` 完全一致。
- 验证：`validate_package.py --root .` 输出 `Package validation passed.`；AGENTS.md 同步校验通过；catalog JSON 解析与规则写入校验通过（两个模型模板均含该规则）。
- 剩余说明：该缓解依赖模型遵循提示词，仍可能偶发；长期更稳妥做法是复杂 agentic 任务使用 `deepseek-v4-pro`，长会话及时 /compact。

## 2026-08-15 a-project-init 增加 Git 仓库类型询问与团队仓库 exclude 规则

- 需求：初始化项目时先确认 Git 仓库状态与类型；AGENTS.md 通用规则增加团队协作仓库的排除跟踪询问。
- 改动：
  - `skills/a-project-init/SKILL.md`：Workflow 增加 Git 状态检查（`git rev-parse --is-inside-work-tree`）；无仓库时询问用户是否 `git init`（同意才执行）；有仓库时询问个人/团队协作类型；仓库类型作为项目级信息写入 AGENTS.md「项目级规则」区（新建经 `--project-rules` 传入，已存在时手动追加/更新）。
  - `skills/a-project-init/templates/general-rules.md`：新增第 7 条规则——团队协作仓库中新增与主业务流程无关文件（测试、个人脚本、文档等）前，先询问用户是否加入 `.git/info/exclude` 不纳入跟踪。
  - 同步到本机 `~/.codex/skills/a-project-init/`（SKILL.md、templates/general-rules.md）。
- 验证：`validate_package.py --root .` 输出 `Package validation passed.`；临时目录真实初始化验证 AGENTS.md 含第 7 条规则与「仓库类型：团队协作仓库」项目级记录。
- 未改动：`init_project_agents.py` 确定性链路保持原样；已有 AGENTS.md 的注入语义不变。

## 2026-08-15 新增使用指南文档与四端适用说明

- 需求：README 明确框架适用 Codex CLI、VS Code 插件、桌面端、ACP 外部协议连接端；docs 新增以真实任务为例的使用指南。
- 改动：
  - `README.md`：标题下定位改为面向四类 Codex 客户端的全局 Vibe Coding 工作流；新增「使用指南」章节，指向 `docs/USAGE.md`。
  - `docs/USAGE.md`：新增完整使用指南。以团队协作机器人项目（ROS 2 主线仓库 + 独立执行器仓库、同一分支多人开发）新增「设备状态采集」为例，贯穿六个环节：初始化工程（生成 .project-log 与 AGENTS.md、Git 仓库检查与类型询问）→ 业务逻辑澄清（功能/技术/双向对齐）→ 技术选型（接口、架构、兼容约束）→ 代码落地（写代码-测试-收集证据-判断）→ 非线性回退（BUG 回到澄清）→ 归档工程（a-project-log-archive 推送至个人知识库）。并介绍 Skills a/b 分级与自动路由、内外双循环等框架特点。
- 验证：`validate_package.py --root .` 输出 `Package validation passed.`。
- 说明：示例场景为通用描述，未引用任何真实项目内部规则或代码内容。
