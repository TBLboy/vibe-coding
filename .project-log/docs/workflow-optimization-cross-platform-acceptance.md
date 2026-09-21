# 跨平台验收记录（Windows 与 Ubuntu）

日期：2026-09-20。范围：TASK-026 跨平台集成验收。目的：为“这套框架在 Windows 与 Ubuntu 上是否可以正常使用”提供可复核的证据，而不是仅凭实现意图判断。

## 1. 验收对象（冻结版本）

- 源码仓库：`D:\Project\vibe-coding`
- 导出快照：`D:\Project\vibe-coding-validation\exports\state027-frozen\source`，239 个文件
- 快照摘要算法（必须按此复算）：对快照内每个文件取内容 sha256，生成行 `"<sha256(file)>  <relpath>"`（两个空格，`relpath` 相对 `source/` 且以 `/` 分隔），按 `relpath` 升序排序，以 LF 连接并在末尾追加一个 LF，再对整体取 sha256。
- 快照摘要（本轮复算）：`8accc9985452b3e169aaee5c5c619aa5ef7e947640c5aa3ba46135c6bd7dac1c`
- 关键文件哈希：`state_store.py` `88bebdfd3577dd801ac1231da25683cd366db4180453ee722719e7ed03915927`；`state_views.py` `abf01e0e9a5a4dac2082d558403bb9262e007d38e7502132066c05fece719091`；`state_context.py` `0ec4f21de659ae60cd30d5e098f1015a10e44a0cbe0e1c49e62cbab9edbf15ed`；`state_exchange.py` `5642dbca795035a6fa319f6ac52fbdb2f1b22d4fcbeb72709bfc3614c9458243`；`state_routing.py` `3b5541291c49ed86e5c530110f627beda9ffd1907ac6371150fa184fe1c093ec`；`state_evidence.py` `1e9623098f62980cba9a52bf910568c2505a6d619ee89b899571e0d8cfecc919`；`state_gate.py` `02cfbcf50b0016341ad1d45491d7df421549399b410343849a4b6ecf3f942d46`；`state_migrate.py` `4e7aa41142b9195267fd428d5d80d78c7406ad9a7dfce95f1a5447e9b9a5187a`；`vibe.py` `c934e241400fe77b397a7b60bd382dc7639a6125154ea550eacc738edfef1bc3`
- 本轮修正：本记录此前给出的快照摘要 `9ee16bc8…` 与 `state_evidence.py` 哈希 `e04ff9ab…` 均不可复现（`e04ff9ab…` 只有 32 个十六进制字符，不是 sha256）。`reviewer-021` 在复核时独立测出 `8accc998…` 并报告摘要不一致；同一算法对更早的 `state027-final`（`5675d323…`）与 `state027-final2`（`97ac9464…`）复算完全一致，说明是记录值过期而非算法错误。上列值已按复算结果更正。
- 运行时代码与当前源码仓库的关系：导出时逐文件比对的差异全部落在 `.project-log/` 下本项目自身的记录文件（收口时为 7 个：`current-session.md`、`progress.md`、`tasks/task-list.yaml`、`docs/workflow-optimization-cross-platform-acceptance.md`、`loop/active-run.yaml`、`loop/handoff.md`、`loop/events.jsonl`），其余 232 个文件字节完全相同，且全部关键模块哈希一致。此后源码前进了 TASK-028 的修复（只涉及 `runtime/scripts/loop_state.py` 与 `tests/test_loop_core.py`），其复验见第 9 节；本节其余结论以本节冻结版本为准。
- 平台：Windows 11 + PowerShell 5.1 + Python 3.11.15（`D:\conda\envs\vibe-coding\python.exe`）；Ubuntu（WSL2）+ Python 3.11.16 + SQLite 3.53.1 + git 2.34.1
- 所有测试、夹具、日志与报告位于 `D:\Project\vibe-coding-validation`；源码仓库在每轮运行后摘要不变（`source_unchanged=True`），真实论文项目与全局安装未被触碰。

## 2. 平台矩阵（全部退出码 0）

| 套件 | 覆盖内容 | Windows | Ubuntu |
|---|---|---|---|
| baseline | 仓库自带测试（安装器、loop core、项目初始化、模板） | 41 项：40 通过 + 1 跳过 | 41 项：40 通过 + 1 跳过 |
| binding | Git diff 字节绑定（无效 UTF-8、二进制、暂存区、空 diff） | 8 通过 | 8 通过 |
| launchers | `vibe.ps1`/`vibe.sh` 入口、解释器解析、安装/更新/卸载 | 16 通过 | 6 通过（`test_unix_launchers.py`） |
| state | 统一状态服务、事务、生成视图、旧写入隔离 | 39 通过 | 39 项：38 通过 + 1 跳过（Windows 专用长路径） |
| crashes | 进程强杀后的恢复语义 | 3 通过 | 3 通过 |
| exchange | 双克隆往返、对抗拒绝、强杀与恢复、并发与外部锁、行尾 | 15 通过 | 15 通过 |
| routing | 风险分流策略、升级条件、最小上下文预算 | 17 通过 | 17 通过 |
| evidence | 历史结果与当前适用性、三种选择器、旧记录转换与绑定保留 | 20 通过 | 20 通过 |
| gate | 反向索引、依赖失效传播、完成门禁、严格复核要求、畸形输入 | 29 通过 | 29 通过 |
| migrate | 迁移预览与可回退演练、回滚包完整性 | 12 通过 | 12 通过 |
| integration | 隔离安装、Hooks 注册、Skill 指令、运行期往返 | 7 通过 | 7 通过 |
| benchmark / metadata | 有界查询基准、包/项目/loop 记录校验 | 通过 | 通过 |

Windows 运行标签：`runs/state027-frozen-{baseline,binding,launchers,state,crashes,exchange,routing,evidence,gate,migrate,integration,metadata}`。Ubuntu 运行标签：`linux/runs/state027-linux-frozen`（单次 `--suite all`，14 项检查全部 exit 0，驱动器退出码 0）。

## 3. 兼容与迁移

- 旧版入口在两种平台上都只做只读恢复并明确拒绝旧写入，未出现“第二套状态被继续写入”的情况（`state`、`baseline` 套件）。
- 旧格式项目不会被自动改写；新格式标记缺失时入口保守拒绝（`test_malformed_marker_fails_closed`、`test_explicit_init_refuses_legacy_and_missing_flag`）。
- 迁移预览与回滚只在临时副本上演练，未触碰真实项目；原 ID、未知字段与历史证据保留（`migrate` 套件）。

## 4. 安装、Hooks 与 Skill 指令

- 隔离安装（临时 `CODEX_HOME` 与 skills 根）在两种平台都成功，安装器 `verify` 通过，安装后的运行期能完成一次真实往返（`integration` 套件）。
- `SessionStart`、`PostToolUse`、`PreCompact` 三个 Hook 均注册且指向实际存在的脚本；Hook 只读，不修改项目（`state` 套件中的 Hook 用例）。
- 全局 `AGENTS.md` 与 `a-engineering-landing`、`a-verification` 两个 Skill 携带的分流策略文本与实现一致（`integration` 套件断言 `任务分流`、`state-route`、`state-context`、`Risk routing`、`budget_insufficient`）。

## 5. 分流一致性（三类任务对照）

同一份策略在两种平台上对同一组输入给出逐字节相同的结果（复算约定：取两个文件里的 `cases` 段，按 `json.dumps(cases, ensure_ascii=False, sort_keys=True)` 序列化后取 sha256，得到 `87e935121fa3807a5c0e6e76af6b6592dc279149ce12c049aa02d2d662fd8e6c`；证据：`runs/state027-routing-compare/windows.json`、`linux/runs/state027-routing-compare/linux.json`）：

| 任务 | 判定 | 最低验证 | 必需记录 |
|---|---|---|---|
| 单文件文档措辞修正（docs-only，1 文件） | `quick` | 1 项 | 1 条 |
| 无高风险信号的普通实现改动 | `standard` | 2 项 | 1 条 |
| 参考文献/投稿格式改动 | `strict` | 3 项（含独立复核） | 2 条 |
| 声明为不可逆的数据改动 | `strict` | 3 项（含独立复核） | 2 条 |

这正是优化目标 2 要的效果：低风险改动不再套用完整生命周期，而高风险或不可逆改动自动升级到严格路径。

## 6. 独立复核

三轮切片级独立复核，全部由独立子代理执行，实现方只负责修复与提供证据；最终发布复核（`reviewer-030`，A1–A8）见第 13 节。

1. `reviewer-020b`（快照 `17c1fca9…`，交换切片首轮）：213 项断言中 204 通过，报出 D1-D9。D1-D4 为代码缺陷（导入接受实体表与账本不一致的快照、导入接受回执与请求矛盾的新命令、待发布期间接受命令导致 `validate()` 误报、导出已发布却报失败且缺失生成视图无法原地修复），D5-D9 为记录漂移。全部修复，并为 D1-D4 增加回归测试，以“回退修复代码后这些测试必然失败”反证其有效性。
2. `reviewer-020d`（交换切片复审）：使用首轮未修改的检查脚本，check2 对抗检查由 39/41 升为 **41/41**（D1、D2 已被拒绝），check3 强杀检查由 37/38 升为 **38/38**（D3 已修复），check1/4/5/6 保持 34/34、18/18、17/17、15/15，合计 211/213。剩余两项失败经复核确认为**探针自身过期**而非产品缺陷：check7 的 “pending revision disagrees” 用例断言的是 D3 已判定为错误的旧不变量（`pending_revision == local_revision`），check8 的计数用例读取的是首轮运行的固定标签。已给出改写方案（合法的滞后 `pending_revision` 必须被接受，0/负数/超过 `local_revision` 必须仍被拒绝；计数用例指向本版本运行）。复核方按该方案改写并重跑：check7 由 34/35 变为 **38/38**（一个被取代的用例换成四个契约一致用例，全部通过），check8 由 14/15 变为 **15/15**（计数用例改指本版本运行，缺失证据时显式报错），八个检查合计 **216/216**、退出码 0，未软化任何期望值。**范围声明**：该轮复审的对象是 `exports/state027-final2/source`（摘要 `97ac9464…`），与第 1 节冻结版本只差 `runtime/scripts/state_evidence.py` 与 `.project-log/docs/workflow-optimization-cross-platform-acceptance.md` 两个文件，二者都不在交换切片内，因此交换切片结论可迁移到冻结版本；本记录不声称该轮复审直接跑在冻结快照上。
3. `reviewer-021`（分流/证据/门禁/迁移切片）：首轮报出 6 项代码缺陷与 1 项文本-代码不一致；修复过程中它又追加三项发现（回滚包丢失 legacy `task-list.yaml` 的 `active_goal` 指针；`check`/`invalidate`/`build_index` 对畸形记录仍会抛原始异常；转换后的旧证据不携带任务/需求绑定）。全部修复后，在冻结版本上复核方的八个探针套件 **88/88 全部通过、0 项矛盾**（routing 8/8、evidence 11/11、gate 17/17、migrate 13/13、integration 11/11、fix-audit 16/16、final-audit 8/8、r04-conversion 4/4）；同一批探针在修复前的更早 revision 上为 76 项中 25 项矛盾，可反证修复确实改变了行为；`runs/SUMMARY.json` 记录的 16 项缺陷全部 `fixed`（含 R-04）。修复内容：`context()` 组装时计入自身簿记并报告真实字节数（此前会超出预算且少报）；无法求值的选择器一律不得判为 `current`，非 JSON 合规字段与畸形选择器改为定义明确的 `StateError`；失效沿 `depends_on` 传递且防环，无法求值的选择器按“无法证明未受影响”上报；复核身份比较忽略大小写与首尾空格；严格门禁要求复核覆盖全部被验收产物（新增 `review_does_not_cover_artifacts`）并绑定任务（新增 `task_identity_required`）；`binary_input` 计入阻断分类；回滚包补齐 legacy decisions/questions/active-goal 及其指针；转换后的旧证据保留 `tasks`/`requirements`/`git_commit`/`diff_hash` 绑定，因此门禁可按任务选中它；畸形 legacy 结构改为上报而非抛出原始异常；缺失根目录明确失败。唯一曾未消项 P6 经查为复核探针把结论写死在代码里，复核方已改为实测并通过。

## 7. 未验证与限制

- 真实项目上的**安装**试点已于 TASK-027 执行（第 12 节）；真实项目日志上的**迁移预演**在只读副本上执行（第 10 节）。该项目自身的写入、迁移 apply、`EV-019` 重验与 `Q-021` 答复仍未执行，属该项目自己的决策。
- Windows 上无符号链接权限，相关守卫只能进程内验证；未覆盖网络文件系统与更深的分支链。
- 未在 macOS 或其他 Linux 发行版上验证；Ubuntu 侧为 WSL2 环境。
- 交换层已知审计边界（复核报告记录）：区间内 `created_sequence`、自由文本 `title`/`extensions`、`base_snapshot` 替换。
- `reviewer-021` 同时报出一处**记录缺陷**：本记录原先声明的冻结快照摘要 `9ee16bc8…` 与 `state_evidence.py` 哈希 `e04ff9ab…` 不可复现。已核实并更正为 `8accc998…` 与 `1e9623098f…`（见第 1 节），并补充了摘要算法定义与“运行时代码与当前源码逐文件一致”的比对结论。
- 复核方书面报告状态：三份报告中两份已落盘——`reviewer-020b/REPORT.md`（首轮 D1-D9）、`reviewer-021/REPORT.md`（八个套件 88/88、0 矛盾、16 项缺陷全部 `fixed`，本记录已按其 `runs/SUMMARY.json` 复算一致）、`reviewer-020d/REPORT.md`（改写后八个检查 216/216，并单独列出提议但未执行的 step-C 对抗探针）。两处曾失败的探针经确认是探针自身过期，不当作产品缺陷关闭。
- `reviewer-021` 的最终报告把 7 项残留列为限制而非缺陷，其中与真实使用相关的是：上下文包在极小预算下会退回丢弃 `omitted` 列表（阻断事实从不丢弃，`used_bytes` 等于真实字节数）；无法求值的选择器按“无法证明未受影响”上报，因此 `stale_count` 可能包含与本次改动无关的记录；`rollback_bundle` 不阻止调用方把目标目录选在项目内（临时副本是调用方责任）；门禁的 `before=` 指纹比较未从 CLI 暴露（属性仍由判定时重新指纹化覆盖）。该报告曾把“历史 69 条证据的迁移”列为未执行项：第 10 节已在真实项目日志的只读副本上完成预演（69/69 无损转换），并更正了“迁移 apply 存在但待授权”的表述——框架有意不提供原地迁移 apply。
- 活跃 Hook 的边界：`post_tool_use` 对新格式项目直接短路（只读设计，已由测试固定，见 `state_context.is_transactional`），因此新格式下的精确失效由门禁/CLI 在判定时执行；旧格式项目仍走旧 `covers.files` 路径规则（`loop_state.invalidate_evidence`），且该语句不声称 Hook 完全不失效。把 `state-gate-invalidate` 接入 PostToolUse 是 TASK-023 已记录的后续项，不是本轮验收项。
- 收口时发现的遗留缺陷（**已在 TASK-028 修复，见第 9 节**）：旧 Loop Core 的 `loopctl start-run` 会重建 active-run 并把 `goal_id` 与原生 Goal 绑定清空，因此“关闭旧 Run、为新任务开 Run”会丢掉 Goal/Run 关联。当时以 `state-repaired` 事件显式登记并把 `goal_id` 恢复为 GOAL-001；随后 TASK-028 修正了 `start_run` 与 `restore_active_run`，并用“放回修复前代码后 2 项测试失败”反证。这属于复核报告 P0-1“Goal/Run/Task 状态机”建议的已处理项。

## 8. 结论

在第 1 节冻结版本上，Windows 与 Ubuntu 的全部套件（含强杀恢复、并发与外部锁、行尾、隔离安装、Hooks 与 Skill 指令一致性、旧格式兼容、有界查询基准与记录校验）均通过且退出码为 0；三类任务对照在两种平台上给出逐字节相同的分流结果。交换切片首轮复核提出的 4 项代码缺陷已由未修改的独立检查脚本复验通过（对抗 41/41、强杀 38/38），过期探针改写后该复核方的八个检查为 216/216、退出码 0；分流/证据/门禁/迁移切片首轮提出的 6 项代码缺陷（含后续追加的 3 项发现）已由复核方自己的八个探针套件复验为 88/88、0 项矛盾。第 9 节记录了此后针对 Run 切换丢失 Goal/Task 绑定的一次增量修复；该修复在 Windows 与 Ubuntu 的回归矩阵上复验通过，本节结论在该修订上同样成立。

## 9. 增补（TASK-028）：Run 切换丢失 Goal/Task 绑定的修复与复验

本节记录第 1～8 节冻结版本之后的一次增量修复。它属于 BL-WFOPT-001（“Goal、Task、Run、阻塞事实和下一步不得互相矛盾”）的已批准范围，不需要新的产品级授权。

**发现**：收口时用 `loopctl start-run --phase verification --task-id TASK-027` 关闭旧 Run（TASK-020-exchange）并开启新 Run，结果新 Run 的 `goal_id` 变为 `null`、原生 Goal 绑定被清空；`restore_active_run(force=True)` 也不会从 `run-started` 事件重放 `task_id`。也就是说，切换 Run 会丢掉 Goal/Run/Task 关联，只能靠手工改 `active-run.yaml` 补回——正是复核报告 P0-1 指出的那类状态漂移。

**修复**（`runtime/scripts/loop_state.py`）：

- 新增 `project_goal_id()`：仅当 `goals/active-goal.yaml` 存在、`goal.id` 合法且状态属于 `draft/active/waiting-user/blocked` 时返回该 ID；已完成（`complete`）的目标不被借用。
- `start_run` 把新 Run 绑定到当前项目 Goal，并在 `run-started` 事件中记录 `goal_id` 与 `native_goal_binding`。
- `restore_active_run` 从 `run-started` 事件重放 `task_id`（此前只重放 run_id/goal_id/phase）。
- 保留既有语义：`native_goal` 仍由 `loopctl goal-bind` 显式建立（README 记录的 start-run → goal-bind 流程不变），`test_start_run_resets_completed_run_state` 继续通过。

**回归测试**（`tests/test_loop_core.py`，4 项）：开放目标时绑定；已完成目标不被借用；无目标时保持未绑定；强制重建重放 goal/task/phase。

**反证**：把修复前的 `loop_state.py`（`a24a2523…`）放回修复后的快照再跑这 4 项测试，2 项失败（`test_start_run_binds_the_open_project_goal`、`test_restore_replays_the_run_goal_and_task_binding`），另 2 项仍通过——它们是不被过度绑定行为的守卫测试。证据：`runs/state028-falsification/report.json`。

**新冻结版本**：`exports/state028-fix/source`，239 个文件，按第 1 节算法复算摘要 `7fc1baeed8603dcc785d918c2f258d18dcca216bfc79b4347077f8ac6fb352de`；关键文件哈希 `loop_state.py` `758eb36299609ba958c7d525145cec4651c8f40b4f62fd8a79a9f241b2d139e7`、`test_loop_core.py` `7faaf1f8165c63e9d19291a485fe6246e5d8b9470e3e04b086da3a805ab14246`。

**复验矩阵（全部退出码 0）**

| 套件 | Windows 标签 | Windows 结果 | Ubuntu 标签 |
|---|---|---|---|
| baseline | `runs/state028-all` | 45 项：44 通过 + 1 跳过 | `linux/runs/state028-linux-wsl` |
| binding | `runs/state028-all` | 8 通过 | 同上 |
| launchers | `runs/state028-all` | 16 通过 | 同上（`test_unix_launchers.py` 6 通过） |
| state（含基准）、crashes、exchange、routing、evidence、gate、migrate、integration、metadata | `runs/state028-<suite>` | 全部 exit 0 | 同上（单次 `--suite all`，14 项检查全部 exit 0） |

Ubuntu 侧由 WSL2 内的 Python 3.11.16 执行，`report.json` 记录 `platform=linux`，被测 `loop_state.py` 哈希为 `758eb362…`。

**未受影响模块**：逐文件比对两个冻结版本，239 个文件里只有 `runtime/scripts/loop_state.py` 与 `tests/test_loop_core.py` 两个运行时文件不同（其余 7 处差异全部落在 `.project-log/` 记录内）。`state_store.py`、`state_views.py`、`state_context.py`、`state_exchange.py`、`state_routing.py`、`state_evidence.py`、`state_gate.py`、`state_migrate.py`、`vibe.py` 的哈希与第 1 节完全一致，因此第 2～6 节对它们的结论继续有效。

**记录更正**：`linux/runs/state028-linux` 是一次误用 Windows 解释器启动 Linux 驱动器的运行（其 `report.json` 记录 `platform=win32`），不作为 Linux 证据，保留以便审计；有效的 Ubuntu 证据是 `linux/runs/state028-linux-wsl`。

**事件日志更正**：用户复盘指出 `.project-log/loop/events.jsonl` 中没有任何 `review-completed` 事件，是“独立验证没有形成闭环”的证据之一。收口时按三份复核产物补登记了 `review-completed`（`LE-000159`～`LE-000161`），payload 内含复核方、范围、被审快照摘要、结论与产物路径，并显式标注 `recorded_at_close_out`，说明这是收口时从复核产物补录，而不是复核发生当时写入。

**补充独立验证（D4 的“视图原地修复”）**：复核报告曾把 `state_views` 的“缺失生成文件原地补写”列为“实现方声明但未独立复现”的残留项。`reviewer-029` 用独立探针在被测快照上复现五条断言，全部 `verified`：

- A：删除生成视图 `handoff.md` → `state-views` 退出码 0、`repaired: ["handoff.md"]`，字节还原且整树摘要回到删除前基线，重跑返回 `repaired: []`（幂等）。
- B：删除生成清单 `manifest.json` → 同样原地补写并报告。
- C / C2：篡改 `current-session.md` 或 `manifest.json` 字节 → `state-views` 以退出码 2 + `projection_incomplete` 拒绝，篡改字节**未被覆盖**，`CURRENT.json` 未变。
- D：Git 工作树下的 `state-export` 同样能原地补写缺失视图。

它同时指出一处**有意差异**（判定为非缺陷）：`state-export` 下同样的投影冲突只以 `projection_error` 上报而退出码仍为 0——因为快照与指针已经落盘，返回非零会诱发重复导出；`docs/USAGE.md` 已如此约定，两条路径的 fail-closed（不覆盖篡改字节）都成立。唯一残余风险是只读退出码的调用方会漏读正文。证据：`reviewer-029/REPORT.md`、`reviewer-029/runs/SUMMARY.json`。

**结论**：第 8 节的结论延伸到 `state028-fix` 修订——Windows 与 Ubuntu 的回归矩阵在修复后仍然全部通过，且 Run 切换不再丢失 Goal/Task 绑定。仍未执行的只有 TASK-027 的安装与试点本身（见第 10 节），需要用户的目标级批准。

## 10. TASK-027 预备：真实项目日志的只读迁移预演

TASK-027 的 apply 需要用户对安装目标与试点项目授权，但它的**预演**不需要。本节对真实论文项目的 `.project-log` 做只读副本预演，关掉“历史证据迁移从未在真实数据上验证”这一限制项，并明确迁移的实际边界。

**方法与不变量**：把 `D:\Project\my_lunwen\.project-log`（96 个文件、9.4 MB）复制到 `task027-dryrun-v2/my_lunwen-copy`，只对副本执行 `state-migrate-preview`。源目录在前后各做一次整树摘要，两次一致（`4d4c4f8550574516…`，96 个文件），因此真实项目未被写入。证据：`task027-dryrun-v2/report.json`。

**预演结果（真实数据）**

| 项目 | 结果 |
|---|---|
| 清单 | 任务 39、决策 17、问题 21、证据 69 |
| `ready` | `true`（0 冲突、0 缺失引用） |
| 未知任务字段 | 39 条（每个任务都带 `acceptance_refs, blocked_by, created_at, owner, priority, required_skills, updated_at`） |
| `unmappable_history` | 无命令信封，不为历史记录编造回执；历史 `passed` 30 条、`unknown` 39 条 |
| 证据转换 | 69/69 成功、0 错误；选择器 220 个且全部带记录摘要 |
| 绑定保留 | `tasks` 68、`requirements` 19、`git_commit` 67、`diff_hash` 67，与旧文件里的非空计数逐项一致，即转换无损 |

**边界更正（重要）**：本记录此前把“真实迁移未执行”写成待授权事项，这不准确。框架**没有**把旧格式项目原地转换为 format 2 的 apply：`state-init` 遇到已有 `.project-log` 会以 `migration_required`（`migration is not available`）拒绝（`state_context.initialize`）。因此 TASK-027 的试点内容是：

1. 在获批目标上安装框架，并验证入口、Hooks、Skills；
2. 让旧格式项目继续走 `loopctl` 链路（新格式入口对它只读恢复并拒绝新格式写入）；
3. 需要评估迁移时使用只读预演与回退包（本节即为真实数据上的预演）。

`docs/USAGE.md` 已新增“旧格式项目与迁移预演”一节，把上述边界与两个预演命令写入用户文档——此前该节缺失，属文档与代码的漂移。

**文档改动的复验**：新增的 `docs/USAGE.md` 一节之后，`integration`（隔离安装、Hooks 注册、Skill 指令一致性、运行期往返）与 `metadata`（包/项目/Loop 校验）重新执行并退出码 0（`runs/state028-doc-integration`、`runs/state028-doc-metadata`）。当前源码相对 `state028-fix` 快照只多出 `docs/USAGE.md` 一处文档差异，加上 `.project-log/` 下本项目自身的记录；运行时代码未再变化。

**结论**：真实项目日志上的迁移预演通过，证据转换在真实 69 条记录上无损；同时确认“没有迁移 apply”是设计边界而不是未完成项。仍未执行的只剩 TASK-027 的安装与试点本身。

## 11. 增补（TASK-029）：实时 Hook 改为按记录哈希精确失效

**发现**：`loop_state.invalidate_evidence` 只做路径交集——工具 payload 里出现某个被覆盖路径，相关证据就一律转 `stale`，从不检查文件是否真的变了。这正是用户复盘 P0-2 的实测现象（69 条证据里 39 条 stale，其中 23 次来自通用的 `PostToolUse:apply_patch`）。复核报告 R-07 也记录了这个分层边界。

**修复**（`runtime/scripts/loop_state.py`）：新增 `covered_bytes_changed()`。被覆盖路径被工具提到时，只有当它的当前字节与 `version_binding.file_hashes` 记录不一致、文件已不存在、或该路径没有记录哈希时才判 `stale`；字节一致则保持 `candidate`/`valid`。保守方向不变：无法证明“未变化”的一律仍按失效处理，因此不会产生 false current。

**回归测试**（`tests/test_loop_core.py`，5 项）：路径被提到但字节未变保持 current；重写为相同内容保持 current；缺少记录哈希仍失效；文件被删除仍失效；未被覆盖的路径不失效。

**反证**：把上一修订的 `loop_state.py`（`758eb362…`）放回后，2 项“保持 current”测试失败、3 项守卫测试仍通过。证据：`runs/state029-falsification/report.json`。

**新冻结版本**：`exports/state029-hook/source`，239 个文件，按第 1 节算法复算摘要 `6fb47037453f81dc9cc85f484c4815e804d2d5f46d4ae43b69e875edcf76466a`；`runtime/scripts/loop_state.py` `7c403182ada0612b8272cb6182b726104ad451b17a96280c9142a4fc1033ff21`。

**复验矩阵（全部退出码 0）**：Windows `runs/state029-baseline`（50 项：49 通过 + 1 跳过）与 `runs/state029-{binding,launchers,state,crashes,exchange,routing,evidence,gate,migrate,integration,metadata}`；Ubuntu `linux/runs/state029-linux-wsl`（14 项检查，`platform=linux`，被测 `loop_state.py` 哈希 `7c403182…`，其中基线 50 项：49 通过 + 1 跳过、状态服务 39 项：38 通过 + 1 跳过）。

**计数更正**：`reviewer-030` 在最终发布复核中指出本记录把基线写成“41/45/50 通过 + 1 跳过”，而 unittest 实际报告的是“运行 41/45/50 项，其中 1 项跳过”，即通过数应为 40/44/49。已按各套件日志的 `Ran N tests` 与 `... ok` 计数逐项复算更正（其余套件 8/3/15/17/20/29/12/7/16/6 与记录一致）。

**R-07 状态**：实质问题已解决——实时 Hook 的失效判定不再是路径交集，而是按记录哈希。它仍不调用 `state_gate.invalidate`；对旧格式项目它通过 `loop_state.invalidate_evidence` 按 `covers.files` 路径规则失效，对新格式项目则只读短路、不执行任何失效。这条分层是有意的，不是遗漏（措辞由 `reviewer-030` 复核后收紧）。

**结论**：第 8～10 节的结论延伸到 `state029-hook` 修订；至此用户复盘里 P0-2“证据失效粒度过粗”在实时路径上也得到处理。

## 12. TASK-027：全局安装与真实项目试点

用户批准“直接全局安装然后做项目试点”。本节记录安装、独立验证，以及在真实项目上的只读试点结果。

**安装前备份**：安装器自身会写 `~/.codex/backups/vibe-global-update-<stamp>`（本次 `vibe-global-update-20260921-090127-697957`，`original_backup_dir` 指向首次安装的备份）。此外在 `task027-install/pre-install-backup/` 另存了一份独立快照（`AGENTS.md`、`config.toml`、`auth.json`、`vibe-python`、`vibe-workflow` 104 个文件、`plugins`，以及 46 个 skill 名），并记录哈希，见 `task027-install/pre-install-backup.json`。回退方式：安装器 `uninstall` 从 `original_backup_dir` 恢复；独立快照可交叉核对。

**preflight**：`blocking_failures: []`；唯一非阻塞项是终端配色（`TERM=dumb`、`NO_COLOR=1`），与本框架无关。

**安装结果**（`global_installer.py install`，退出码 0）：

- 运行时同步到 `~/.codex/vibe-workflow`（116 个文件），`loopctl.py` 哈希与源码仓库一致（`ec118000…`）
- `AGENTS.md` 更新（13285 → 15372 字节），含 `VIBE-CODEX-GLOBAL` 标记、任务分流一节与八荣八耻
- Hooks：`SessionStart`、`PostToolUse`、`PreCompact` 均注册，绑定 `~/.codex/vibe-python` 指向的解释器，同时写 `command` 与 `commandWindows`
- MCP `codegraph`；marketplace `vibe-global-toolbox`；插件 `vibe-toolbelt 0.4.1`
- skills：46 → 46（集合未变）
- `verify`：退出码 0（`Global installation verification passed.`）

**真实项目试点（`D:\Project\my_lunwen`，只读）**：先把 `.project-log`（96 个文件）整目录备份到 `task027-pilot/project-log-backup/`，再执行 `status`、`validate`、`restore`、`state-migrate-preview`、`state-route`、`evaluate goal`。**运行前后文件清单逐项一致，未写入任何字节**（`task027-pilot/phase-a.json` 的 `changed_after_readonly_checks: []`）。

试点发现（对该项目有实际价值）：

1. **目标完成状态与机器判定不一致**：`goals/active-goal.yaml` 的 `status` 是 `complete`，但 `loopctl evaluate goal` 返回 `passed: false`，原因是 `SC-004` 依赖的 `EV-019` 已失效（`status: stale`，失效时间 2026-09-18，原因正是 `PostToolUse:apply_patch`），另有未决 C 级问题 `Q-021`。
2. **失效原因印证 P0-2**：`EV-019` 覆盖 6 个 `.project-log` 文件，仅因通用 `apply_patch` 的路径交集被判 stale——正是 TASK-029 修复的场景。
3. **证据健康状况**：69 条证据中 30 valid / 39 stale。
4. **分流可用**：`state-route --path main.tex --signal submission-format` 输出 `strict`，最低验证包含独立复核，与优化目标 2 一致。
5. **待用户输入**：`Q-021`（C 级、critical，关联 TASK-030：RAS 标题页与声明所需的作者名单、CRediT、单位地址、通信邮箱、资助声明与生成式 AI 使用状态）与 `Q-016`（A 级：软体平台设备照片）仍未决。

**边界**：本节对真实项目的操作全部只读；`EV-019` 的重新验证、`Q-021` 的答复以及目标状态的更正都属于该项目自己的决策，未代为执行。

**结论**：全局安装与验证在真实环境完成；框架在真实项目上能恢复状态、给出分流结论，并抓出“目标声明完成、但依赖证据已失效且存在未决 C 级问题”的假完成。这正是 TASK-027 要验证的真实使用收益。

据此可以对本轮范围下定论：**这套框架在 Windows 与 Ubuntu 上均可正常使用**，前提与边界是——本结论覆盖第 1 节冻结版本与第 2 节列出的套件范围，并经第 13 节的最终发布复核（`reviewer-030`，A1–A8 全部 `verified`、结论 GO）确认；真实项目的安装与只读试点（TASK-027）已完成，见第 12 节；仍未执行的只有该项目自身的迁移 apply、`EV-019` 重验与 `Q-021` 答复，属该项目自己的决策；两处复核探针的收尾改写不影响已复验的产品行为。

## 13. 最终发布复核（reviewer-030）

`reviewer-030` 对当前修订 `exports/state029-hook` 做发布前独立复核：八项断言全部 `verified`、0 项矛盾，结论 **GO**。产物：`reviewer-030/REPORT.md`、`reviewer-030/runs/SUMMARY.json`，探针 `probe_1_2.json`、`probe_3_counts.json`、`probe_A4_{falsify,control}.log`、`probe_A6.json`、`probe_A7.json`、`probe_A8.json`。

| 断言 | 内容 | 结论 |
|---|---|---|
| A1 | 按第 1 节算法复算快照摘要 | verified：`6fb47037…` 一致（239 文件，摘要 blob 25790 字节） |
| A2 | `loop_state.py` 哈希 | verified：快照 = 仓库 = `7c403182…`（32906 字节），并与 `state029-baseline` 报告一致 |
| A3 | 在快照上跑仓库自测 | verified：`Ran 50 tests … OK (skipped=1)`、退出码 0，即 50 运行 / 49 通过 / 1 跳过 |
| A4 | 反证回归测试是否 load-bearing | verified：独立把 `loop_state.py` 回退为上一修订后复现失败（退出码 1，`['EVID-001'] != []`），原始快照同一测试通过（退出码 0） |
| A5 | 安装校验 | verified：`verify` 退出码 0；独立复算 `~/.codex/AGENTS.md` sha256 `9252246f…`（15372 字节）；`SessionStart`/`PostToolUse`/`PreCompact` 三个 Hook 均注册且同时有 `command` 与 `commandWindows` |
| A6 | 试点只读性 | verified：`changed_after_readonly_checks: []`；96 个实时文件 / 96 个备份文件，0 路径差异、0 哈希差异，清单为 `backup-manifest.json`（96 条） |
| A7 | 真实项目发现 | verified：`EV-019` `status: stale` + `invalidation_reason: PostToolUse:apply_patch`；`active-goal.yaml` 目标 `status: complete`；`Q-021` `status: open` / `authority: C`；只读 `evaluate goal` 的三条理由与第 12 节一致；96 个文件整树摘要前后不变（`63046a15…`） |
| A8 | R-07 措辞与 Hook 实现 | verified：`post_tool_use.py` 中 `state_gate` 出现 0 次，唯一失效调用是 `loop_state.invalidate_evidence`；第 7、11 节的措辞已按复核建议收紧 |

**复核边界**：未覆盖 macOS 与其他 Linux 发行版、无符号链接权限与网络文件系统场景，以及第 12 节所记录之外的安装 apply。复核期间 `vibe-coding`、`my_lunwen` 与 `~/.codex` 均只读（`my_lunwen` 整树摘要不变）。

## 14. 增补（TASK-030）：Python 引导改为原地修复显式解释器

**背景**：Q-001（C 级）问“已显式配置的解释器不可用时，安装/更新器能否改选命名 Conda 环境”。用户选择“原地修复、绝不静默换环境”，答复见 `business-logic/open-questions.yaml`；决策记录 `DEC-008`。

**发现**：`scripts/bootstrap_vibe_python.py` 在显式配置的解释器依赖检查失败时会改用命名 Conda 环境并重写 `CODEX_HOME/vibe-python`，属于静默替换用户的显式选择。而日常运行入口（`vibe.ps1`/`vibe.sh`）与 `global_installer.py` 都是 fail-closed，且后者文档声明该文件**不被安装器管理**；当 `VIBE_PYTHON` 环境变量被设置时，写入的配置文件甚至不生效。三处策略不一致。

**修复**（`scripts/bootstrap_vibe_python.py`）：

- `configured_python()` 返回解释器及其来源（`VIBE_PYTHON` 或配置文件）。
- 新增 `python_version_ok()`，用于区分“版本合格但缺依赖”与“根本不是 3.11+”。
- 已配置解释器只缺依赖时：把依赖装进该解释器，并保持 `vibe-python` 不变。
- 已配置解释器不是 3.11+ 或不可执行时：明确报错并给出可执行的修复命令，不创建也不改选 Conda 环境。
- 只有显式 opt-in（`VIBE_PYTHON_REPAIR` 取值为 `1`/`true`/`yes`/`on`，或 `--repair-interpreter`）才改选命名 Conda 环境并重写配置；其它取值（含 `0`、`false`）不生效。
- `VIBE_PYTHON` 环境变量优先时拒绝重写配置文件。
- 无配置时的首次安装与 `--no-create`（uninstall）行为不变。

**回归测试**（`tests/test_installer.py`，5 项）：原地修复且不重写配置；pip 无法修复时拒绝且不创建环境；显式 opt-in 才切换并重写配置；`VIBE_PYTHON` 优先时拒绝重写；配置路径不存在时不创建环境并给出出路提示；假值 `VIBE_PYTHON_REPAIR` 不触发 opt-in。

**反证**：把最初修订的 `bootstrap_vibe_python.py`（`24b61567…`）放回后，**5 项测试全部失败**；把上一修订（`0b38f8cd…`）放回后，F1（假值 opt-in）与 F2（缺失路径提示）两项失败、其余 3 项通过——两次修复都是 load-bearing。证据：`runs/task030c-falsify-vs-state029/report.json`、`runs/task030c-falsify-vs-fix2/report.json`。

**冻结版本**：`exports/task030-fix3/source`，239 个文件，按第 1 节算法复算摘要 `33765c8d090370d0923c3436a1edc167f251e7bf69cec05a2fe619464cf98db2`；`scripts/bootstrap_vibe_python.py` `9f3fe49f36092e784d2ca050a4caba19a95708f4ef6de87f8762bbecb47dfdcd`。

**复验矩阵（全部退出码 0）**：Windows `runs/task030c-baseline`（55 项：54 通过 + 1 跳过，含 5 项新测试）与 `runs/task030c-{binding,launchers,state,crashes,exchange,routing,evidence,gate,migrate,integration,metadata}`；Ubuntu `linux/runs/task030-linux-wsl4`（14 项检查，`platform=linux`，基线 55 项：54 通过 + 1 跳过，被测 `loop_state.py` 哈希 `7c403182…`）。

**记录更正**：`exports/task030-fix` 是在 TASK-030 写入任务清单之前导出的（`records` 因悬空引用失败，见 `linux/runs/task030-linux-wsl2`）；`exports/task030-fix2` 早于复核提出的 F1/F2 修复。两者都不作为最终证据，保留以便审计；最终冻结版本是 `exports/task030-fix3`。

**复验驱动调整**：Linux 驱动的单命令超时由 300s 提升到 1200s——此前基线已用 264.6s，加入新测试后达到 356s，旧上限会把正常运行误判为超时。这是复验工具调整，不影响被测框架行为。

**独立复核（reviewer-031）**：A1–A7 全部 `verified`——反证可独立复现；策略 1–5 逐条读码成立，且未发现任何无需显式 opt-in 就会改写配置或创建 Conda 环境的路径；Windows 基线 55 项；冻结摘要复算一致；被取代运行仅 `records` 失败；Ubuntu 14 项全 0；记录层互相一致。复核提出并已处置：

- **F1（中）** `VIBE_PYTHON_REPAIR=0`/`false` 仍会 opt-in——已改为只接受 `1`/`true`/`yes`/`on`，并加回归测试。
- **F2（低）** 配置路径缺失时的报错缺少出路——已在失败路径补上可执行提示，并加断言。
- **F3（高）** 单一事实源未更新——已用 `loopctl start-run` 为 TASK-030 开新 Run（自动绑定 `GOAL-001`），登记 TASK-030 事件并重建 handoff。
- **F4（高）** 被 `passed` 条件引用的证据已不适用——已按框架规则精确失效 `PYTHON-001`、`MCP-006`、`MCP-007`、`STATE020-SLICE`、`REVIEW-STATE020-V5`、`RUNBIND-028`，并登记锚定当前修订的 `PYTHONREPAIR-030`、`STATESLICE-030`、`PLATFORM-030`；`SC-001` 与 `SC-004` 的证据引用已改指新证据。
- **F5（低）** TASK-030 的 `verification.status` 与结果不一致——收口时改为 `passed` 并绑定上述证据。

**复核增量（reviewer-031，第二轮）**：对 `exports/task030-fix3` 的 V1–V7 全部 `verified`——F1 修复经 17 个输入探针验证（假值不 opt-in、`--repair-interpreter` 仍生效、flag 优先）；F1/F2 两项测试在上一修订上确实失败；冻结摘要与文件数复算一致；Windows 55 项与 Ubuntu 14 项全部退出码 0；证据适用性审计在目标层为 **0 条“被 passed 条件引用的 valid 证据已漂移”**；全部校验器与 `evaluate goal` 通过。结论：**TASK-030 GO，关闭 GOAL-001 GO**。第二轮新增处置：

- **F7（高）** `loop/handoff.md` 未重建——已重建（现为 `Task: TASK-030`、`Run status: complete`、`Open C questions: none`，并带精确 next action）。
- **F8（低）** `PYTHON-002`/`PYTHON-003` 无记录哈希、货币性不可证——保留为历史证据；其“入口/配置存在”的结论已由 `PLATFORM-030`/`PYTHONREPAIR-030` 在当前修订上重新锚定。
- **F9（中）** 没有绑定 TASK-030 改动文件的 `kind: review` 证据——已登记 `GOALREVIEW-031`（`kind: review`、`subject: goal-final-review`，覆盖 `scripts/bootstrap_vibe_python.py` 与 `tests/test_installer.py`），并加入 `SC-007` 与 `required_evidence`。
- **F6（中）** 配置路径不可用时的提示指向了在该状态下无法生效的动作——属行为/措辞变更，已登记为 `TASK-031`（`pending`，B 级），不作为本轮关闭条件。

**遗留边界**：覆盖 `.project-log` 记录文件的证据不会因每次日志编辑而重新失效（本轮只对运行时/产品文件执行了精确失效）。这属于用户复盘中 P0-2/P1-2 的“证据范围语义化”后续项，已记入 TASK-030 的 limitations。

**结论**：显式配置的解释器不再被静默替换；三条链路（日常入口、安装器主体、安装/更新引导）现在采用一致的 fail-closed 策略，唯一例外是用户显式 opt-in。第 13 节与本节共同覆盖的当前修订是 `exports/task030-fix3`。

## 15. 增补（TASK-031）：引导失败提示只给出可执行动作

**来源**：`reviewer-031` 的 F6——`ensure_python` 的 `except` 分支在 `selected` 赋值之前抛出，因此提示里的 `VIBE_PYTHON_REPAIR=1` 在该状态下无法生效；另外 `VIBE_PYTHON="   "` 会给出配置文件路径的提示。

**修复**（`scripts/bootstrap_vibe_python.py`）：

- `configured_python()` 改为返回 `(interpreter, source, problem)`，不再对畸形取值抛异常；空白 `VIBE_PYTHON` 仍归因到环境变量，空配置文件报告 problem。
- 新增 `unusable_hint()`：按来源给出出路（环境变量来源 → 取消或修正它；配置文件来源 → 修路径或 opt-in 切换），不再提示一个做不到的动作。
- 新增 `switch_interpreter()`：把 opt-in 的提示集中到一处。
- `ensure_python()` 重构：**配置路径本身不可用**且显式 opt-in 时，真正回落到命名 Conda 环境并重写配置；未 opt-in 时仍然 fail-closed、不写任何东西。
- 无 Conda 时的失败信息改为说明“已配置的解释器不可用且找不到 Conda，因此 opt-in 也无法切换”。

**回归测试**（`tests/test_installer.py`，新增 2 项并重定向 1 条断言）：配置路径不可用 + opt-in 会切换并重写配置；空白 `VIBE_PYTHON` 的提示归因到环境变量且不写文件；`VIBE_PYTHON` 优先时断言可执行提示并确认没有宣布切换。

**反证**：把上一修订的 `bootstrap_vibe_python.py`（`9f3fe49f…`）放回后，恰好这 2 项新测试失败、其余 5 项通过——修复是 load-bearing。证据：`runs/task031-falsify-vs-fix3/report.json`。

**冻结版本**：`exports/task031-fix/source`，239 个文件，按第 1 节算法复算摘要 `a309d075ad458006d8735e4926e2f96def98019128bfcf44a23f234c4003a65d`；`scripts/bootstrap_vibe_python.py` `5a9c6cf8f3a4c3fc0c3660e068ee9299706d53d3dde6faa19ac6b5644becbdff`。

**复验矩阵（全部退出码 0）**：Windows `runs/task031-baseline2`（57 项：56 通过 + 1 跳过，含 7 项 bootstrap 测试）与 `runs/task031-{binding,launchers,state,crashes,exchange,routing,evidence,gate,migrate,integration,metadata}`；Ubuntu `linux/runs/task031-linux-wsl`（14 项检查，`platform=linux`）。

**独立复核（reviewer-031，第三轮）**：W1–W4、W6、W7 全部 `verified`；W5 的 Windows 半边 verified、Linux 半边在其给出结论时仍在运行（随后由 `linux/runs/task031-linux-wsl` 补齐为 14 项 exit 0）。结论：**TASK-031 代码 GO**。同轮报出：

- **X1（高，记录层）** 本修订使被 `passed` 条件引用的证据失效（`SC-004` ← `PYTHONREPAIR-030`/`PLATFORM-030`，`SC-007` ← `GOALREVIEW-031`）——已按规则失效这三条，登记绑定当前修订的 `PYTHONHINT-031`、`PLATFORM-031`、`GOALREVIEW-032`，并把 `SC-004`/`SC-007`/`required_evidence` 改指新证据。
- **X2（低）** 无 Conda 时会先打印“正在切换”再失败——提示顺序问题，本轮未改。
- **X3（低-中，先于本轮存在）** `find_conda`/`env_python` 接受“退出码 0 但打印错误”的管理器，把错误文本当成解释器路径（本机 `D:\conda\Library\bin\conda.bat`）——已登记为 `TASK-032`。
- **X4（信息）** 被取代的 `runs/task031-baseline`（针对重定向前断言的运行）与权威的 `baseline2` 并存，保留以便审计。

**结论**：引导脚本失败时给出的每个动作都在该状态下真实可执行；显式配置的解释器仍不会被静默替换。
