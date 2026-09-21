# Progress

## 当前状态

- 当前阶段：GOAL-002 落地收口；TASK-032..TASK-044 与 TASK-047 已完成，TASK-045 第二轮独立复核进行中
- 当前任务：TASK-045 第二轮复核中；TASK-046（本仓库自身日志迁移）为 C 级授权关口，未获授权
- 当前状态：新项目默认 format 2；版本单一来源 `runtime/scripts/framework_info.py`（0.5.0）；门禁按当前字节重算证据适用性；迁移切换幂等可续跑；记录载荷任意深度长正文被拒；旧格式只读有迁移指引、写入有弃用提示；未迁移、未安装、未提交
- 业务基线：`BL-FRAMELAND-001..009` + `REQ-001`（approved）+ `DEC-009`（C 级，用户已批准）+ `ARCH-002`
- 最近验证：`unittest` 126 项（125 通过 + 1 跳过）、`validate_project`、`validate_package`、`loopctl validate`、`git diff --check` 全通过；当前修订证据 `RECORDS-036C`/`GATES-037C`/`HOOKS-039C`/`MIGRATE-040C`/`VALIDATE-041C`/`LINUX-043C`/`FIXES-047`/`SUITE-044B`/`ROUND1-045`
- 下一步：等 TASK-045 第二轮的 GO/NO-GO；GO 后安装到本机 Codex 并申请 commit / push；TASK-046 与 Windows 实机矩阵仍分别未授权、未验证

## 2026-09-21 TASK-045 第一轮 NO-GO 与 TASK-047 修复

- 第一轮独立复核（源码树外冻结副本，180 文件哈希全通过）给出 **NO-GO**：AC-FL-007/008/010/017 失败，AC-FL-016/018 部分未验证。
- D-001 高风险任务缺实现者身份或复核未绑定证据仍可完成 → 现在必须记录实现者且存在绑定当前有效证据的 `go` 复核。
- D-002 覆盖产物变化后门禁仍放行 → 现在门禁直接重算证据适用性，失效证据不支撑任务与目标完成。
- D-003 中断迁移无法续跑 → 切换改为“状态库→旧文件→布局→标记”幂等顺序，标记是唯一提交点，`resume` 可恢复“标记存在但状态库缺失”的现场。
- D-004 嵌套 `payload.meta.body` 绕过长正文限制 → 递归拒绝任意深度超限字符串。
- D-005 迁移缺 `.state/`、`.gitignore`、`exchange/.gitattributes` → 补齐与 `vibe init` 相同的布局，回退清理迁移自建布局。
- 契约澄清：`docs/` 是两种格式共用的长正文位置，迁移不搬走（原第 7 节措辞与第 4 节冲突，已在契约中记录）。
- AC-FL-016 保持 partial：校验器现在重算记录 `doc_ref.sha256` 并报告不一致，但未做到自动失效无关证据。
- 验证：126 项测试（1 跳过）与三个校验器通过；D-006（Windows）仍为 implemented-unverified。

## 2026-09-21 TASK-044：安装、升级、卸载与旧格式退役机制

- 版本单一来源 `runtime/scripts/framework_info.py`（0.5.0 / 默认 format 2 / store schema 3 / 退役三阶段），安装器与发布脚本改为引用它；`vibe version`、`vibe --version` 输出同一身份。
- 旧格式只读兼容：`loopctl status|validate` 与 `vibe status` 在 format 1 项目输出 `legacy format: migrate with vibe migrate`；format 1 写入仍可用但在 stderr 输出弃用提示。
- 退役关口：`docs/RELEASE-NOTES.md` 固化 `stop-writing` / `stop-reading` / `stop-support`，每阶段 `gate: user-approval`、`status: pending`；真实项目与本仓库自身日志迁移都需独立显式授权。
- 安装链路：安装/升级/卸载在 Linux 上可重复执行，安装打印默认 format 2 与迁移指引，卸载声明项目 `.project-log/` 未被改动；测试验证三连操作后旧格式项目字节不变。
- 验证：`unittest` 117 项（1 跳过）、三个校验器与 `git diff --check` 全通过；`tests/test_release_surface.py` 7 项在 `e236fda` 上 7/7 失败；TASK-040 反证 7/7、TASK-041 4/5、TASK-042 3/3、TASK-043 2/3 失败。
- 证据维护：按规则失效 13 条覆盖文件已变化的旧证据，登记 11 条绑定当前修订的新证据（含 `RELEASE-044`、`SUITE-044`）。
- 边界：Windows 实机矩阵未验证；退役阶段未被实际执行；本仓库 `.project-log` 仍为 format 1；改动未提交、未安装。

## 2026-09-21 TASK-032/034/035：开始落地

- TASK-032：修复 `env_python` 把零退出码的错误输出当成解释器路径（reviewer-031 X3），新增 `probe()` 让不可执行目标返回诊断；4 项回归测试，反证 4/4 在 `e236fda` 失败。
- TASK-034：冻结 format 2 生产契约（实体模型、ID 规则、长文档边界、命令与门禁、CLI 面、迁移状态机、跨平台约束、AC-FL 映射）；架构新增 `ARCH-002`；迁移对不可映射历史改为保留区而非中止，并同步细化 TASK-040 的 `done_when`。
- TASK-035：默认初始化切到 format 2，新增 `vibe init`，`state-init` 成为兼容别名；标记不再写 `experimental` 但兼容旧标记；初始化铺好长摘要与归档说明；`hook_common` 不再在 format 2 项目创建旧 YAML。反证：8 项新测试在 `e236fda` 上 8/8 失败。
- 验证：`unittest` 70 项（1 跳过）、`validate_project`、`validate_package`、`loopctl validate` 全通过。
- 边界：只在本机 Linux 验证；format 1 仍可显式生成；Hook 的 format 2 恢复属 TASK-039。

## 2026-09-21 新框架彻底落地：记录业务逻辑并拆解任务（TASK-033）

- 远端复核：本地与 `origin/main` 同在 `e236fda`，无更新超出该提交；工作区此前干净。
- 记录：新增 9 条原子业务逻辑 `BL-FRAMELAND-001..009`、决策 `DEC-009`、需求基线 `REQ-001`、活动目标 `GOAL-002`；GOAL-001 归档到 `goals/archive/GOAL-001.yaml`。
- 拆解：新增 TASK-034..TASK-046，覆盖默认初始化切换、完整生命周期实体、证据与复核门禁、统一入口与旧写入口保护、Hooks 与会话恢复、可执行迁移、校验器、规则资产与文档、跨平台验收、安装与退役机制、独立发布评审、本仓库自身日志迁移；依赖无环，除 TASK-033 外全部 `pending`。
- 冲突处置：`BL-PROJECTINIT-001` 的旧约束与新方向冲突，显式置为 `deprecated` 并记录取代；`DEC-004` 同类约束在 `DEC-009` conditions 中标注待更新，未静默覆盖。
- 验证：`validate_project`、`validate_package`、`loopctl validate` 通过，`unittest` 57 项（1 跳过）；证据 `LANDING-033`。
- 边界：本轮只交付规划产物与项目日志；`BL-FRAMELAND` 验收条目全部 `not-verified`，不代表任何实现已完成。

## GOAL-001 收口快照（历史，2026-09-21）

- 当前阶段：GOAL-001 已结算完成；TASK-031 亦已完成（唯一遗留是 TASK-032，pending，B 级）
- 当前任务：TASK-001..TASK-031 全部完成（done），含 TASK-027（全局安装与真实项目试点）、TASK-030（Python 引导原地修复显式解释器）与 TASK-031（失败提示只给可执行动作）；TASK-032 待办
- 当前状态：当前修订 `exports/task031-fix`（摘要 `a309d075…`）在 Windows 与 Ubuntu 上全部回归套件退出码 0；Q-001 已由用户答复并落地（`DEC-008`）；按框架规则失效 3 条漂移证据并登记 3 条锚定当前修订的新证据；`SC-004`/`SC-007` 证据引用已更新
- 最近验证（当前修订 `exports/task031-fix`）：Windows 基线 57 项（56 通过 + 1 跳过）、绑定 8、入口 16、状态 39、强杀 3、交换 15、分流 17、证据 20、门禁 29、迁移 12、安装集成 7、元数据通过；Ubuntu `linux/runs/task031-linux-wsl` 14 项检查全部退出码 0（基线 57 项：56 通过 + 1 跳过）；`state027-frozen`/`state029-hook`/`task030-fix3` 的矩阵保留为历史基线；失败与被取代记录全部保留
- 下一步：
  - TASK-032（pending，B 级）：让 `find_conda`/`env_python` 拒绝“退出码 0 但打印错误”的管理器（`reviewer-031` 的 X3）
  - 工作区改动尚未提交，待用户决定是否 commit / push

## 2026-09-21 TASK-031：引导失败提示只给可执行动作

- 来源：`reviewer-031` 的 F6；修复 `scripts/bootstrap_vibe_python.py`，使配置路径不可用 + 显式 opt-in 时真正回落命名 Conda 环境并重写配置，未 opt-in 仍 fail-closed，提示按来源给出可执行动作。
- 新增 2 项回归测试并重定向 1 条断言；反证：上一修订恰好这 2 项失败、其余 5 项通过。
- 冻结修订 `exports/task031-fix`（摘要 `a309d075…`）；Windows `runs/task031-*` 全部 exit 0，Ubuntu `linux/runs/task031-linux-wsl` 14 项 exit 0。
- 第三轮独立复核 W1–W4/W6/W7 verified、代码 GO；X1 已通过证据重新锚定解决，X2 未改，X3 → TASK-032，X4 保留为审计记录。

## 2026-09-21 TASK-030：Python 引导原地修复显式解释器（Q-001 落地）

- 用户对 Q-001 选择“原地修复、绝不静默换环境”；`DEC-008` 记录该决定与选项。
- `scripts/bootstrap_vibe_python.py`：显式配置的解释器只缺依赖时原地安装依赖且不改配置；不是 3.11+ 或不可执行时报错并给出出路；只有显式 opt-in（`VIBE_PYTHON_REPAIR` 为 `1`/`true`/`yes`/`on`，或 `--repair-interpreter`）才改选命名 Conda 环境并重写配置；`VIBE_PYTHON` 优先时拒绝重写。
- 5 项回归测试；反证：最初修订 5/5 失败，上一修订仅 F1/F2 两项失败（两次修复均 load-bearing）。
- 冻结修订 `exports/task030-fix3`（摘要 `33765c8d…`）；Windows `runs/task030c-*` 全部 exit 0，Ubuntu `linux/runs/task030-linux-wsl4` 14 项 exit 0。
- 独立复核 `reviewer-031` 的 A1–A7 全部 verified，并提出 F1–F5；F1/F2 已改代码并复验，F3/F4/F5 已在记录与 Loop 状态层收口。

## 2026-09-21 最终发布复核（reviewer-030）

- `reviewer-030` 对 `exports/state029-hook` 做发布前独立复核：**A1–A8 全部 verified、0 项矛盾、结论 GO**；产物 `reviewer-030/REPORT.md` 与 `reviewer-030/runs/SUMMARY.json`。
- 已登记 `GOALREVIEW-030`（`kind: review`、`subject: goal-final-review`、`status: valid`），`SC-007` 置为 `passed`、`required_evidence.independent-review` 指向它；`evaluate goal` 由四条理由降为一条（`open C-level questions: Q-001`）。
- 唯一措辞问题（R-07 可被误读为“Hook 完全不失效”）已按复核建议收紧；验收记录新增第 13 节。

## 2026-09-21 收口：任务关闭与证据更正

- TASK-020..TASK-026 状态改为 `done`（`verification.status: passed`）；TASK-027 保持 `pending`（C 级授权）。
- 复核报告：三份 `REPORT.md` 均已落盘（reviewer-020b / reviewer-020d / reviewer-021）；reviewer-021 为八个探针套件 88/88、0 矛盾、16 项缺陷全 `fixed`，reviewer-020d 改写两处过期探针后为 216/216。
- 证据更正：验收记录原声明的冻结摘要 `9ee16bc8…` 与 `state_evidence.py` 哈希 `e04ff9ab…` 不可复现，已更正为 `8accc998…` 与 `1e9623098f…`；逐文件比对确认运行时代码与当前源码一致。
- Loop 状态：Run 由 TASK-020-exchange 切换为 TASK-027/verification 并 handoff；`start_run` 清空 `goal_id` 的遗留缺陷已用 `state-repaired` 事件登记恢复。

## 2026-09-21 TASK-028：Run 绑定修复

- 修复 `loopctl start-run` 切换 Run 时丢失 `goal_id` 与不重放 `task_id` 的缺陷（`runtime/scripts/loop_state.py`），新增 4 项回归测试，并用“放回修复前代码后 2 项测试失败”反证其有效。
- 复验：Windows `runs/state028-all` 与 9 个单独套件全部 exit 0；Ubuntu `linux/runs/state028-linux-wsl` 14 项检查全部 exit 0。验收记录新增第 9 节。
- 误用 Windows 解释器启动 Linux 驱动器的 `linux/runs/state028-linux` 保留为审计记录，不作为 Linux 证据。

## 2026-09-21 TASK-027 预备：真实项目日志只读迁移预演

- 在 `my_lunwen` 的只读副本上跑 `state-migrate-preview`：`ready=true`、0 冲突、0 缺失；任务 39 / 决策 17 / 问题 21 / 证据 69；证据转换 69/69 无损（绑定保留与旧文件计数逐项一致）。
- 更正边界：框架没有旧格式原地迁移 apply（`state-init` 遇已有 `.project-log` 报 `migration_required`），TASK-027 的试点是安装 + 旧格式兼容 + 按需只读预演；`docs/USAGE.md` 补上“旧格式项目与迁移预演”一节。
- 复验：`integration`、`metadata` 在文档改动后重跑退出码 0。

## 2026-09-21 TASK-029：实时 Hook 精确失效

- 把 `loop_state.invalidate_evidence` 从“路径交集即失效”改为“被覆盖文件字节与记录哈希不一致才失效”，并新增 5 项回归测试；反证确认 2 项 load-bearing。
- 复验：Windows `runs/state029-*` 全部 exit 0（baseline 50 项：49 通过 + 1 跳过）；Ubuntu `linux/runs/state029-linux-wsl` 14 项检查全部 exit 0。验收记录新增第 11 节。

## 2026-09-21 TASK-027：全局安装与真实项目试点

- 用户批准后完成全局安装：`install` 与 `verify` 均退出码 0；AGENTS.md、Hooks、MCP、marketplace、插件、skills 全部就位；安装前有安装器备份与独立快照两份。
- 真实项目 `my_lunwen` 只读试点：96 个日志文件前后逐项一致（未写入）；`evaluate goal` 抓出假完成——目标标 `complete` 但 `EV-019` 已 stale（原因 `PostToolUse:apply_patch`）且 `Q-021` 未决。
- 补登记 TASK-021～026 引用却缺失的 6 个证据；GOAL-001 的 SC-001～SC-006 置为 passed。验收记录新增第 12 节。

## 2026-09-21 第二轮复核与跨平台验收

- 交换切片复核（reviewer-020d，未修改的首轮脚本）：对抗 41/41、强杀 38/38，D1-D3 复验通过；两项失败确认为探针过期，待复核方改写后出报告。
- 分流/证据/门禁/迁移复核（reviewer-021）：6 项代码缺陷已修复并由复核方自己的探针复验为 8/8、11/11、17/17、12/12；P6 为探针写死结论，待改为实测。
- 跨平台验收记录：`docs/workflow-optimization-cross-platform-acceptance.md`（冻结版本 `exports/state027-final`，摘要 `5675d323…`）；Windows 与 Ubuntu 全部套件退出码 0。TASK-027 安装与试点仍需用户批准。

## 2026-09-20 交换切片独立复核与修复

- reviewer-020b：213 项断言 204 通过，D1-D9 已全部修复（代码 4 项 + 记录漂移 5 项），新增 D1-D4 回归测试并反证有效。
- 证据：runs/state027-*、linux/runs/state027-linux-all（report.json 全部 exit 0）、reviewer-020b/REPORT.md。

## 2026-09-20 首批实现与外部验证

- 契约：specs/workflow-optimization-contract.md；Git 修复和平台入口已落源代码，SQLite 尚未进入生产。
- 证据根目录：D:/Project/vibe-coding-validation；源码未被测试产物污染，真实论文项目和全局安装未修改。
- 详细进度与失败保留见 current-session.md；后续不是重复原测试，而是事务/并发/快照原型。

## 2026-09-19 四项优化任务拆解

- `.project-log/docs/workflow-optimization-task-plan.md` 描述四批任务和 G1/G2 两个关口；机器任务状态以 task-list.yaml 为准。
- TASK-014 是开工后的第一个候选；当前禁止自动执行。原型、代码实现、安装和迁移均未开始。

## 2026-09-19 四项框架优化技术选型

- RES-001 给出候选比较、统一状态接口、风险分流、证据指纹策略和分阶段验收。
- 详细方案：`.project-log/docs/workflow-optimization-technical-selection.md`。
- DEC-006 仅为提议：SQLite/文本快照方案须先经用户确认并完成隔离原型；不在真实论文项目试验。

## 2026-09-07T15:40:00+08:00 将八荣八耻口诀加入通用 Agent 规则

- 状态：实现与当前 Codex 同步完成；提交待用户确认。
- 变更：`prompts/vibe-global-agent.md` 与 `skills/a-project-init/templates/general-rules.md` 新增“八荣八耻”；通过安装器同步到 `~/.codex/AGENTS.md` 与已安装 skill 模板。
- 验证：41 个 unittest（1 跳过）、包校验、项目校验、Loop 校验全部通过；已安装文件核对一致。
- 备注：第 7 条原文“以诚实无知为菜”修正为“以诚实无知为荣”。
- 下一步：用户确认后提交并推送 main。

## 2026-08-20T17:45:00+08:00 固化 project-log 长文档组织约定

- 状态：实现与本地验证完成；提交待用户确认。
- 变更：project-log 两个长摘要模板加入“最新在最上、头部快照、超限归档、单一事实源、机器维护文件不手工重排”规则；`a-project-log`、`a-session-handoff`、`docs/USAGE.md`、`prompts/vibe-global-agent.md` 同步约定；`validate_package.py` 将模板纳入必选运行时资产；新增 `tests/test_project_templates.py`。
- 验证：`python -m unittest discover -s tests -p 'test_*.py' -q` -> 41 passed, 1 skipped；`validate_package.py`、`validate_project.py`、`loopctl validate` 全部通过。
- 下一步：提交并推送 `main`（用户确认后）。

## 2026-08-14T22:17:00+08:00 Stop-after-status-update root cause

- Status: root cause confirmed from local rollout and log evidence; no framework code changed.
- Symptom: after the user sent "继续", the model checked Hook hashes, then returned only a status message and stopped.
- Evidence: `rollout-2026-07-27T21-26-37-019fa3c1-74a0-7693-97de-209b5b918788.jsonl` shows `task_complete` immediately after the assistant message at `22:11:18.554Z`.
- Turn evidence: no ERROR; `full_context_window_limit_reached=false`; `token_limit_reached=false`; `model_needs_follow_up=false`.
- Conclusion: primarily model behavior; Codex ends the turn when no follow-up tool call is emitted. Vibe Hooks did not fail in that turn.
- Next step: if it recurs, retry with an explicit "continue and execute the next commands" prompt, or add a framework guard for active-run status-only completion.

## 2026-08-13T11:30:00+08:00 Loop recovery and new-run repair

- Status: implementation and current-Codex installation complete; source commit pending.
- Fixed SessionStart state contamination: context rendering is read-only, completed and empty runs are not restored as active work, and `PreCompact` is the lifecycle point that persists a durable handoff.
- Added `loopctl start-run --task-id <id>` to reset old task, next action, counters, and native Goal binding while retaining prior evidence and event history.
- Fixed hook project root selection so an explicit workspace root wins and a newly created child directory does not inherit a parent `.project-log`.
- Verification: 31 unit tests passed with 1 expected historical skip; package validation passed; source and installed runtime hashes match; installed SessionStart/PreCompact and `start-run` smoke tests passed; global installer verification passed.
- Limitation: full source project-log schema validation remains blocked by pre-existing malformed historical records; the framework code tests and package validation are clean.

## 2026-08-02T09:30:00+08:00 Push closeout

- User requested a temporary stop to the MCP/Codex terminal investigation and asked to preserve the current work.
- Recorded the completed MCP encoding/proxy compatibility fixes, Codex hook compatibility fixes, and their validation evidence.
- Prepared the current tracked changes for commit and push to origin/main; push fallback is http://127.0.0.1:10808.
- Commit `cf2b80b` was created and pushed successfully to `origin/main` through `127.0.0.1:10808`; final worktree verification is pending.

## 2026-08-05T21:30:00+08:00 Windows host cc-switch config and hook sync

- Status: completed on this Windows host; repository changes are not yet committed.
- Regenerated `cc-switch-common-config-codex.txt` for the local host with the configured Python, hooks, and marketplace paths.
- Updated `scripts/generate_cc_switch_config.py` to emit the host header comment, matching the tracked template intent.
- Re-ran the global installer update with `--access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt --skip-preflight`; installed hook hashes match `runtime/hooks/` and verification passed.
- Validation: TOML parses; generator output is identical to the tracked file; `pytest tests\test_loop_core.py -q` -> `13 passed`; `pytest tests\test_installer.py -q` -> `10 passed, 1 skipped`.
- Next step: commit and push if the Windows template is to be kept as the tracked example.

## 2026-08-14T22:10:00+08:00 Pull, merge, and framework install

- Status: completed; changes are not committed per user request.
- Pulled remote `53d611d` which adds loop run lifecycle fixes (`start-run`, stale-state prevention) and hook context improvements.
- Merged local hook fixes (UTF-8 streams, graceful degradation, cc-switch generator header) with the remote update; conflicts resolved.
- Installed the merged update into `C:\Users\12187\.codex` via `global_installer.py update --access-profile keep-existing --mcp codegraph --mcp vibe-toolbelt`.
- Validation: installed hooks/scripts hashes match source; `loopctl validate` passed; hook tests `21 passed, 4 subtests`; installer tests `10 passed, 1 skipped`.
- Next step: user decides whether to commit and push the merged changes.

## 2026-08-05T22:00:00+08:00 SessionStart hook exit code 1 fix

- Status: implemented and verified on this Windows host.
- Symptom: interactive Codex reported `SessionStart hook (failed): hook exited with code 1` after the protocol fix.
- Root cause: the hook process crashed while initializing project-log state for a non-ASCII/invalid payload path (PermissionError), and stdin was decoded with the console codepage instead of UTF-8.
- Changes: `runtime/hooks/hook_common.py` reconfigures stdin/stdout to UTF-8; `session_start.py` and `pre_compact.py` catch project-state failures and return fallback context with exit code 0.
- Changes: added `test_hooks_tolerate_non_ascii_payloads` regression coverage.
- Validation: failing payload repro now exits 0 and returns valid JSON; `pytest tests\test_loop_core.py -q` -> `14 passed, 4 subtests`; `pytest tests\test_installer.py -q` -> `10 passed, 1 skipped`; `codex exec --ephemeral --json` returns OK.
- Next step: user restarts the Codex terminal and confirms the TUI no longer shows the hook error.

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

## 2026-08-02T08:40:00+08:00 document-loader MCP ????

- ????? `.mcp.json` ?? `awslabs.document-loader-mcp-server@latest`?cc-switch/Codex ?????????? `127.0.0.1:10808`?????/??????? MCP `initialize`???? `connection closed: initialize response`?
- ??????????? `awslabs.document-loader-mcp-server@1.0.17`??? MCP ?? `HTTP_PROXY`/`HTTPS_PROXY`?????? Codex 0.145.0 ???? `PostToolUse.async` ? `PreCompact.additionalContextLimit`?
- ???`pytest tests\test_installer.py -q` ? `10 passed, 1 skipped`??? MCP `initialize` ?? `Document Loader 3.4.5`??? `codex exec --ephemeral --json '??? OK'` ?? `OK`???? `0`???????????
- ???????? `global_installer.py update --access-profile keep-existing --skip-preflight`?????? `C:\Users\12187\.codex\config.toml` ????
- ????? `config.toml` ?? `SessionStart`/`PostToolUse` ? `additionalContextLimit`?? `PreCompact` ??????????? Codex ???????????

## 2026-08-03 宿主机配置动态化

- 状态：已完成实现与验证，待提交并推送 `origin/main`。
- 根因：`cc-switch-common-config-codex.txt` 仍包含 Windows 用户路径和 Windows 仓库路径，不能直接用于当前 Ubuntu 宿主机，也不能安全跨机器复制。
- 改动：新增 `scripts/generate_cc_switch_config.py`，从 `CODEX_HOME`、`VIBE_PYTHON`/`CODEX_HOME/vibe-python`、当前源码根目录动态生成 cc-switch Codex 通用配置；Ubuntu 的 `command` 与 `commandWindows` 使用当前实际路径，Windows 宿主机分别生成对应字段。
- 改动：将 `cc-switch-common-config-codex.txt` 更新为当前 Ubuntu 实际配置，并注明必须在目标宿主机重新生成，禁止跨机器直接复制绝对路径。
- 宿主证据：`CODEX_HOME=/home/tbl/.codex`，Vibe Python=`/home/tbl/miniforge3/envs/vibe-coding/bin/python`，源码根=`/home/tbl/Project/vibe-coding`。
- 验证：生成结果与 canonical 配置正文一致；TOML 解析和宿主路径断言通过；Windows 硬编码扫描通过；安装器测试 `10 passed, 1 skipped`；包校验通过。
- 下一步：提交动态配置生成器、Ubuntu 配置示例和本次项目记录，推送 `main`。

## 2026-08-03 SessionStart Hook 协议修复

- 状态：已完成实现、安装和验证；本地工作区存在待提交修改，未自动推送。
- 根因：`session_start.py` 和 `pre_compact.py` 返回旧式顶层 `{"additionalContext": ...}`；当前 Codex SessionStart Hook 要求使用 `hookSpecificOutput.hookEventName` 声明事件名，否则提示 `hook returned invalid session start JSON output`。
- 改动：SessionStart 返回 `hookSpecificOutput = {hookEventName: "SessionStart", additionalContext: ...}`；PreCompact 使用对应的 `PreCompact` 事件名。
- 改动：更新 `tests/test_loop_core.py`，严格验证事件专用输出结构和事件名。
- 验证：Hook 专项测试 `13 passed`；安装器测试 `10 passed, 1 skipped`；包校验通过；本机受管 Hook 哈希与源码一致；直接 SessionStart 协议校验通过；Codex ephemeral 冒烟返回 `OK`，退出码 `0`。
- 本机安装：已运行 `global_installer.py update --mcp codegraph --mcp vibe-toolbelt --access-profile keep-existing`，安装器校验通过。
- 下一步：用户重新开启一个 Codex 对话确认 TUI 层提示消失；如需纳入远端，再提交并推送。


## 2026-08-14 SessionStart Hook 根因修复

- 状态：已修复并验证。
- 根因：Codex 0.147.0 对 Hook command 不再做 shell 引号解析，带引号命令行无法启动进程。
- 改动：本地 `~/.codex/config.toml` 三个 Hook 命令去引号；清除旧 trusted_hash。
- 验证：`codex exec` 输出 `SessionStart Completed`；Hook 直连 exit 0；哈希与源码一致。
- 下一步：用户在终端实际开新会话确认无 hook 报错；如安装器重装则需同步无引号命令格式。


## 2026-08-14 部署文档补充 Windows Hook 适配

- 状态：已完成并验证。
- 改动：AI_INSTALL.md / AI_UPGRADE.md / README.md 新增 Windows 专属 Hook 命令适配说明；框架源码未改。
- 验证：validate_package 通过。
- 下一步：按需提交并推送这些文档改动。
