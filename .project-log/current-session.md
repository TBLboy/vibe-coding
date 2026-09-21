# Current Session

## 当前状态

- 当前阶段：GOAL-001 已结算完成；TASK-031 亦已完成（唯一遗留是 TASK-032，pending，B 级）
- 当前目标：GOAL-001（四项优化交付并在源码之外完成完整验证）——`status: complete`；SC-001..SC-007 全部 `passed` 且引用有效证据（SC-001 指 `STATESLICE-030`/`GOALREVIEW-030`，SC-004 改指 `PLATFORM-031`/`PYTHONHINT-031`，SC-007 含 `GOALREVIEW-030`/`GOALREVIEW-032`）
- 当前任务：TASK-001..TASK-031 全部完成，含 TASK-027（全局安装与真实项目试点）、TASK-030（Python 引导原地修复显式解释器）与 TASK-031（失败提示只给可执行动作）；TASK-032 待办
- 当前状态：当前修订 `exports/task031-fix`（摘要 `a309d075…`，`bootstrap_vibe_python.py` `5a9c6cf8…`）在 Windows 与 Ubuntu 上全部回归套件退出码 0；Q-001 已答复并落地；TASK-031 修掉了 `reviewer-031` 的 F6；按框架规则失效了 3 条漂移证据并登记锚定当前修订的 3 条新证据
- 最近验证（当前修订 `exports/task031-fix`）：Windows 基线 57 项（56 通过 + 1 跳过）及全部套件退出码 0；Linux（WSL Ubuntu，Python 3.11.16）`linux/runs/task031-linux-wsl` 14 项检查全部退出码 0；第三轮独立复核 `reviewer-031` 的 W1–W4/W6/W7 全部 verified、TASK-031 代码 GO。历史矩阵见验收记录第 2、9、11、14 节。跨平台验收记录见 `docs/workflow-optimization-cross-platform-acceptance.md`
- 下一步：
  1. TASK-032（pending，B 级）：让 `find_conda`/`env_python` 拒绝“退出码 0 但打印错误”的管理器（`reviewer-031` 的 X3）
  2. 工作区改动尚未提交，待用户决定是否 commit / push；真实项目 `my_lunwen` 的 `EV-019` 重验与 `Q-021` 答复仍属该项目自己的决策

## 2026-09-21 TASK-031：引导失败提示只给可执行动作

- 来源：`reviewer-031` 的 F6——`ensure_python` 的 `except` 分支在 `selected` 赋值前抛出，提示里的 `VIBE_PYTHON_REPAIR=1` 无法生效；空白 `VIBE_PYTHON` 还会给出配置文件路径的提示。
- 修复：`configured_python` 返回 `(interpreter, source, problem)`；新增 `unusable_hint`/`switch_interpreter`；配置路径不可用 + 显式 opt-in 时真正回落命名 Conda 环境并重写配置，未 opt-in 仍 fail-closed。
- 新增 2 项回归测试并重定向 1 条断言；反证：上一修订恰好这 2 项失败、其余 5 项通过。
- 冻结修订 `exports/task031-fix`（摘要 `a309d075…`）；Windows `runs/task031-*` 全部 exit 0，Ubuntu `linux/runs/task031-linux-wsl` 14 项 exit 0。
- 复核第三轮：W1–W4/W6/W7 verified，代码 GO；X1（记录层）已通过失效 3 条 + 登记 3 条新证据并改指 `SC-004`/`SC-007` 解决；X2 未改；X3 登记为 TASK-032；X4 保留为审计记录。

## 2026-09-21 TASK-030：Python 引导原地修复显式解释器（Q-001 落地）

- 用户对 Q-001（C 级）选择“原地修复、绝不静默换环境”；决策 `DEC-008`。
- 修复 `scripts/bootstrap_vibe_python.py`：显式配置的解释器只缺依赖时原地安装依赖并保持配置不变；不是 3.11+ 或不可执行时报错并给出出路；只有显式 opt-in（`VIBE_PYTHON_REPAIR` 取 `1`/`true`/`yes`/`on`，或 `--repair-interpreter`）才改选命名 Conda 环境并重写配置；`VIBE_PYTHON` 优先时拒绝重写。
- 新增 5 项回归测试；反证：最初修订 5/5 失败，上一修订仅 F1/F2 两项失败。
- 冻结修订 `exports/task030-fix3`（摘要 `33765c8d…`）；Windows `runs/task030c-*` 全部 exit 0，Ubuntu `linux/runs/task030-linux-wsl4` 14 项 exit 0。
- 独立复核 `reviewer-031`：A1–A7 全部 verified；提出 F1（假值 opt-in）、F2（缺失路径提示）、F3（单一事实源未更新）、F4（证据适用性）、F5（状态与结果不一致），全部已处置。
- 证据维护：按框架规则精确失效 `PYTHON-001`、`MCP-006`、`MCP-007`、`STATE020-SLICE`、`REVIEW-STATE020-V5`、`RUNBIND-028`；登记 `PYTHONREPAIR-030`、`STATESLICE-030`、`PLATFORM-030`；`SC-001`/`SC-004` 引用改指新证据。

## 2026-09-21 最终发布复核（reviewer-030）

- `reviewer-030` 对当前修订 `exports/state029-hook` 做发布前独立复核：**A1–A8 全部 verified、0 项矛盾、结论 GO**。产物 `reviewer-030/REPORT.md`、`reviewer-030/runs/SUMMARY.json` 与 `probe_1_2/A4/A6/A7/A8` 探针。
- 关键复核点：快照摘要 `6fb47037…` 与 `loop_state.py` `7c403182…` 复算一致；快照自测 `Ran 50 tests … OK (skipped=1)`；反证回退后测试确实失败（load-bearing）；安装 `verify` 退出码 0 且 `~/.codex/AGENTS.md` sha256 独立复算一致；试点 `changed_after_readonly_checks: []`、96/96 文件零差异；`my_lunwen` 的 `EV-019`/目标状态/`Q-021` 与第 12 节描述逐条吻合。
- 复核提出的唯一措辞问题（R-07 可被误读为“Hook 完全不失效”）已按建议收紧，见验收记录第 7、11 节；验收记录新增第 13 节。
- 已登记证据 `GOALREVIEW-030`（`kind: review`、`subject: goal-final-review`、`status: valid`），并把 `SC-007` 置为 `passed`、`required_evidence.independent-review` 指向它；`loopctl evaluate goal` 由四条理由降为一条（`open C-level questions: Q-001`）。
- 边界：未覆盖 macOS 与其他 Linux 发行版、无符号链接权限与网络文件系统场景；`my_lunwen` 的 `EV-019` 重验、`Q-021` 答复与目标状态更正属该项目自己的决策，未代为执行。

## 2026-09-21 收口：任务关闭、复核报告与证据更正

- TASK-020..TASK-026 在冻结版本上通过后状态改为 `done`（`verification.status: passed`）；TASK-027 保持 `pending`，属 C 级授权。
- 三份独立复核报告均已落盘：`reviewer-020b/REPORT.md`（首轮 D1-D9）、`reviewer-021/REPORT.md`（八个探针套件 88/88、0 矛盾、16 项缺陷全部 `fixed`，含 R-04；R-01..R-03、R-05..R-07 作为限制保留）、`reviewer-020d/REPORT.md`（改写后八个检查 216/216，并列明提议未执行的 step-C 探针）。
- reviewer-020d 的两处过期探针按契约改写：check7 由 34/35 变为 38/38（合法滞后 `pending_revision` 被接受，0/负数/超范围仍被拒绝），check8 由 14/15 变为 15/15（计数用例指向 `state027-frozen-*`）。
- 证据更正：验收记录原声明的冻结摘要 `9ee16bc8…` 与 `state_evidence.py` 哈希 `e04ff9ab…` 不可复现，已更正为 `8accc998…` 与 `1e9623098f…` 并补充摘要算法定义；逐文件比对确认运行时代码与当前源码一致，仅 `.project-log/` 下 4 个本项目记录文件不同。
- Loop 状态：旧 Run（TASK-020-exchange）由 `start-run` 替换为 TASK-027/verification 并 handoff；`start_run` 会清空 `goal_id`，已用 `state-repaired` 事件登记恢复为 GOAL-001（记为本框架遗留缺陷，本轮未改动代码）。

## 2026-09-21 TASK-028：Run 切换丢失 Goal/Task 绑定的修复与复验

- 缺陷：`loopctl start-run` 切换 Run 时清空 `goal_id` 与原生 Goal 绑定，`restore_active_run(force=True)` 也不重放 `task_id`，导致 Goal/Run/Task 关联丢失，只能手工改 `active-run.yaml`（复核报告 P0-1 那类漂移）。
- 修复：`runtime/scripts/loop_state.py` 新增 `project_goal_id()`（只绑定 draft/active/waiting-user/blocked 的项目 Goal，不借用已完成目标）；`start_run` 绑定 Goal 并在 `run-started` 事件记录 `goal_id`/`native_goal_binding`；`restore_active_run` 重放 `task_id`。`native_goal` 仍由 `goal-bind` 显式建立，README 记录的 start-run → goal-bind 流程不变。
- 回归测试 4 项（`tests/test_loop_core.py`）；反证：把修复前的 `loop_state.py` 放回后其中 2 项失败（另 2 项为防过度绑定的守卫测试），证据 `runs/state028-falsification/report.json`。
- 复验：Windows `runs/state028-all`（baseline 45 项：44 通过 + 1 跳过、binding 8、launchers 16）与 `runs/state028-{state,crashes,exchange,routing,evidence,gate,migrate,integration,metadata}` 全部 exit 0；Ubuntu `linux/runs/state028-linux-wsl` 14 项检查全部 exit 0（`platform=linux`，Python 3.11.16）。
- 记录更正：`linux/runs/state028-linux` 是误用 Windows 解释器启动 Linux 驱动器的无效运行（`platform=win32`），不作为 Linux 证据，保留以便审计。
- 端到端验证：重新执行 `start-run` 后新 Run 自动带 `goal_id: GOAL-001`，无需手工补写；随后 `goal-bind` + handoff 把状态置为等待用户批准 TASK-027。

## 2026-09-21 TASK-027 预备：真实项目日志的只读迁移预演

- 对 `D:\Project\my_lunwen\.project-log`（96 文件 / 9.4 MB）的只读副本执行 `state-migrate-preview`；源目录前后整树摘要一致（`4d4c4f85…`），真实项目未被写入。
- 结果：`ready=true`、0 冲突、0 缺失引用；清单为任务 39 / 决策 17 / 问题 21 / 证据 69；39 个任务都带新格式未知字段（`acceptance_refs, blocked_by, created_at, owner, priority, required_skills, updated_at`）；历史 30 条 `passed`、39 条 `unknown` 归入 `unmappable_history`。
- 证据转换：69/69 成功、0 错误；绑定保留 `tasks` 68、`requirements` 19、`git_commit` 67、`diff_hash` 67，与旧文件非空计数逐项一致；220 个选择器全部带记录摘要。
- 边界更正：框架**没有**旧格式原地迁移 apply（`state-init` 遇已有 `.project-log` 报 `migration_required`）；TASK-027 的试点是安装 + 旧格式兼容 + 按需只读预演。`docs/USAGE.md` 已新增“旧格式项目与迁移预演”一节。
- 复验：`integration` 与 `metadata` 在文档改动后重跑退出码 0（`runs/state028-doc-integration`、`runs/state028-doc-metadata`、`runs/state028-final-metadata`）。

## 2026-09-21 TASK-029：实时 Hook 改为按记录哈希精确失效

- 缺陷：`loop_state.invalidate_evidence` 只按路径交集失效，工具 payload 提到被覆盖路径就判 stale（用户复盘 P0-2：39/69 stale，23 次来自通用 `apply_patch`）。
- 修复：新增 `covered_bytes_changed()`，只有当前字节与 `version_binding.file_hashes` 记录不一致、文件缺失或缺少记录哈希时才判 stale；保守方向不变。
- 回归测试 5 项；反证：放回上一修订的 `loop_state.py`（`758eb362…`）后 2 项失败、3 项守卫通过。
- 复验：Windows `runs/state029-baseline`（50 项：49 通过 + 1 跳过）与 `runs/state029-{binding,launchers,state,crashes,exchange,routing,evidence,gate,migrate,integration,metadata}` 全部 exit 0；Ubuntu `linux/runs/state029-linux-wsl` 14 项检查全部 exit 0（`platform=linux`）。
- 验收记录新增第 11 节；R-07 的实质问题（失效粒度过粗）在实时路径上已解决，Hook 仍不调用 `state_gate.invalidate`（对新格式只读短路）是有意的分层。

## 2026-09-21 TASK-027：全局安装与真实项目试点（用户已批准）

- 安装前备份：安装器写 `~/.codex/backups/vibe-global-update-20260921-090127-697957`（`original_backup_dir` 指向首次安装备份）；另在 `task027-install/pre-install-backup/` 独立快照并记哈希。preflight 无阻塞项。
- 全局安装（`install` 与 `verify` 均退出码 0）：运行时 116 文件且 `loopctl.py` 哈希与源码一致；`AGENTS.md` 更新（13285→15372 字节，含任务分流与八荣八耻）；Hooks（SessionStart/PostToolUse/PreCompact）注册并绑定 vibe-python；MCP `codegraph`、marketplace `vibe-global-toolbox`、插件 `vibe-toolbelt 0.4.1`；skills 46→46。
- 真实项目只读试点：先整目录备份 `.project-log`（96 文件）到 `task027-pilot/project-log-backup/`，再跑 `status`/`validate`/`restore`/`state-migrate-preview`/`state-route`/`evaluate goal`；**前后文件清单逐项一致，未写入任何字节**。
- 试点发现：目标文档标 `complete`，但 `evaluate goal` 返回 `passed=false`——SC-004 依赖的 `EV-019` 已 stale（失效原因正是 `PostToolUse:apply_patch`），且 `Q-021` 未决；69 条证据 30 valid / 39 stale；`state-route --path main.tex --signal submission-format` 给出 `strict`。
- 可追溯性补登：TASK-021～026 引用却从未登记的 6 个证据（ROUTING-021、EVIDENCE-022、GATE-023、REVIEW-GATE-024、MIGRATE-025、CROSSPLATFORM-026）已补登记；GOAL-001 的 SC-001～SC-006 更新为 `passed` 并绑定有效证据。

## 2026-09-21 第二轮独立复核与跨平台验收

- reviewer-020d 用首轮未修改的检查脚本复核交换切片：对抗 41/41（D1、D2 已拒绝）、强杀 38/38（D3 已修复）、其余 34/34、18/18、17/17、15/15；剩余两项失败经复核确认为探针过期（check7 断言的是 D3 已推翻的旧不变量，check8 读的是首轮运行标签），已要求复核方改写后出报告。
- reviewer-021 复核分流/证据/门禁/迁移切片，报出 6 项代码缺陷：上下文包超出预算且少报字节数；无法求值的选择器仍被判 current；非 JSON 合规字段与畸形选择器抛原始异常；失效不沿 depends_on 传递；复核身份比较区分大小写；严格门禁不校验复核覆盖范围与任务绑定。全部修复后复核方自己的探针为 8/8、11/11、17/17、12/12；唯一未消项 P6 经查是探针把结论写死。
- 跨平台验收：Windows 与 Ubuntu 全部套件退出码 0，三类任务对照在两端逐字节一致（cases sha256 `87e93512…`）。真实项目迁移与安装试点（TASK-027）仍未执行，需要用户对具体目标明确批准。

## 2026-09-20 交换切片独立复核与缺陷修复

- reviewer-020b 对快照 17c1fca9… 执行 213 项断言：204 通过，报出 D1-D9。D1/D2（哈希一致但实体表与账本不一致、回执与请求矛盾的快照仍被接受）已在导入写入前加入共享账本重放（Store._verify_ledger），拒绝时事务回滚、本机字节不变；D3（待发布期间接受新命令会让 validate 误报损坏）改为 0 < pending_revision <= local_revision；D4（导出已发布却报失败、缺失的生成视图无法原地修复）改为投影错误隔离加缺失文件原地补写（repaired）。
- D5-D9 为记录漂移：docs/USAGE.md 的“导出导入尚未开放”、交换规格的账本/实体与 CLI 过期结论、TASK-020.md 的过度声明、本会话摘要的过期计数，均已按当前事实改写。
- 新增 D1-D4 回归测试（交换 15、状态 39），并用“回退修复代码后这些测试必然失败”反证其有效性；Windows 与 Linux 全部 suite 重跑通过。未提交、未安装、未迁移真实项目。

## 2026-09-20 外部验证和首批修复

- G1 首轮 NO-GO：原型在存储获取与分支取样之间可跨分支发布；合法哈希快照也可污染原命令回执。两项独立失败现场保留在 reviewer-g1，原型未接入生产。
- 修复重试：增加 Git index 协作锁和项目/分支/存储绑定；增加命令/事件/回执语义一致性与历史不可变校验。Windows/Linux 新故障回归和限定独立复核均通过。任意强制修改 .git 不在协作锁保证内，硬杀可能留下需人工核实的锁，不自动删除。生产是否采用此边界为 Q-002。
- PowerShell 7.4.6 通过外部便携包补测；宿主 -File 会预拆带盘符的等号参数，原始失败保留。入口明确拒绝歧义并建议分开传参，直接脚本调用等号形式经正确数组 splatting 验证可用。PS5/7 各 16 项最新用例通过，不把宿主限制冒充已修复。
- TASK-020 生产规格和 ARCH-001 已形成草案；按实体 SQLite、事务后摘要、显式快照同步均尚未实现。未改变本机安装，未迁移真实论文项目，未提交推送。

- 实施授权已覆盖此前仅规划暂停；旧条目作为历史保留，不再代表当前暂停。
- 所有测试快照、用例、临时安装和报告位于 D:/Project/vibe-coding-validation；my_lunwen 未修改。
- Git 修复独立复核发现损坏分支引用问题，修复后 28/28 通过；失败报告仍在 reviewer-015/REPORT.md，成功报告为 REPORT-v2.md。
- Linux 通过真实 WSL Ubuntu 与外部隔离 Python 3.11 验证，不是把 Windows 工作流静默切到 WSL。发现 CRLF 安装故障，新增 .gitattributes 约束 sh 使用 LF。
- Windows 测试核对 source_unchanged=true；未更新用户全局安装，未提交或推送。

## 2026-09-19 四项优化任务拆解（TASK-013）

- 用户认可 SQLite 与 Git 文本快照方向，同时明确本轮只拆解任务、暂不执行。
- 产物：`.project-log/docs/workflow-optimization-task-plan.md`；TASK-014 至 TASK-027 的待执行任务图；BL-WFOPT-001..004 细化验收草案。
- 两个关口：TASK-019 独立原型评审通过后才进入生产实现；TASK-026 发布验收后还需用户批准 TASK-027 的实际安装/迁移。
- 下一步：等待用户明确开工；不自动恢复实施，不写论文项目，不运行原型，不安装。
- 计划检查：依赖无环、四目标覆盖、14 项实施任务 pending；Project Log 校验通过。检查仅涉及规划产物，不代表各任务已实现。

## 2026-09-19 四项优化技术选型（TASK-012）

- 依据：用户提供的复盘和 D:/Project/my_lunwen 的只读核查；论文项目没有修改。
- 产物：`.project-log/docs/workflow-optimization-technical-selection.md`；RES-001；待批准的 DEC-006。
- 推荐：统一命令服务、显式跨对象转换、自动摘要、前置风险分流、历史结果与当前适用性分离；SQLite 作为需原型验证的存储首选，单文档 JSON 作为 Git 约束下的替代候选。
- 边界：没有实现新 CLI、修改运行时、安装更新或迁移任何项目；没有把数据库方案视为用户已批准。
- 验收：文档定义事务故障、幂等、Git 双副本/分支往返、CRLF/二进制、选择器和独立 review 等 12 项拟议测试，不声称已执行这些测试。
- 权威下一步以 loop/handoff.md 和 active-run.yaml 为准；历史 TASK-011 的未提交同步记录保留。

## 2026-09-09 拉取远端并落地 TASK-011 更新（本地同步）

- 需求：远端更新了 vibe-coding，用户要求拉取并把更新内容落地到本地安装。
- 拉取：直连 fetch 超时，经 `HTTP_PROXY=http://127.0.0.1:10808` 代理 fetch 成功；工作树干净，`git merge --ff-only origin/main` 快进至 `7b32d6f`（feat: add eight-honors rule to general agent guidance）。
- 落地：运行 `D:\conda\envs\vibe-coding\python.exe scripts\global_installer.py update`，成功安装 Vibe Coding - Codex Global Core 0.4.1 至 `C:\Users\12187\.codex`，备份在 backups/vibe-global-update-20260909-204601-983290。
- 验证：update 前本机 `~/.codex/AGENTS.md` 未含八荣口诀（本机安装滞后）；update 后已安装 AGENTS.md 与已安装 a-project-init/templates/general-rules.md 均含“八荣八耻”完整 8 条（关键词检查 `八荣`/`荣`/`耻` 命中）；installer 未回退 Windows hook 修复，config.toml 中 `commandWindows` 保持无引号；直接执行 session_start.py hook 退出码 0。
- 说明：远端提交内容同时落到 `prompts/vibe-global-agent.md` 与 `skills/a-project-init/templates/general-rules.md`，第 7 条按句式写作“以诚实无知为荣”。
- 记录时间：2026-09-09T21:05:00+08:00。

## 2026-09-07 将八荣八耻口诀加入通用 Agent 规则（TASK-011）

- 需求：用户要求把八条“八荣八耻”工作口诀加入 vibe-coding agents 文件的通用规则。
- 范围：同时落到全局 Agent 提示（`prompts/vibe-global-agent.md` -> `~/.codex/AGENTS.md`）和项目通用规则模板（`skills/a-project-init/templates/general-rules.md` -> 已安装 skill）。
- 处理：第 7 条原文“以诚实无知为菜”按八荣八耻句式修正为“以诚实无知为荣”。
- 验证：`global_installer.py update --access-profile keep-existing` 通过；`~/.codex/AGENTS.md` 与已安装 general-rules 均包含完整口诀；包校验、项目校验、Loop 校验和 41 个 unittest 通过。
- 记录时间：2026-09-07T15:40:00+08:00。


## 2026-08-20 固化 project-log 长文档组织约定（TASK-010）

- 需求来源：`boss_electrics/.project-log/docs/log-file-organization-task.md` 描述的长 Markdown 摘要组织问题。
- 范围决策：用户明确不整理已有项目的 `.project-log`，只优化 vibe-coding 框架源码。
- 实现：在 `runtime/project-log-template/{progress.md,current-session.md}` 中加入“最新在最上、头部快照、超限归档、单一事实源、机器维护文件不手工重排”五条维护规则；`a-project-log` 的 `SKILL.md`/`REFERENCE.md`、`a-session-handoff` 同步同一约定；`docs/USAGE.md` 与 `prompts/vibe-global-agent.md` 增加用户与主 Agent 可见的短规则；`validate_package.py` 把两个模板纳入必选运行时产物；新增 `tests/test_project_templates.py` 回归测试。
- 验证：41 个 unittest（1 个历史跳过）通过；`validate_package.py`、`validate_project.py`、`loopctl validate` 全部通过。
- 记录时间：2026-08-20T17:45:00+08:00。


## 2026-08-16 归档 vibe-coding 并修复归档脚本

- 已按 a-project-log-archive 归档 vibe-coding 到 `My_knowledge_base/工程记录/vibe-coding/.project-log` 并推送知识库。
- 归档时发现脚本使用 `git add -A`，把知识库根 `.project-log` 与未提交学习记录一并纳入提交；已恢复根 `.project-log` 位置，并推送修复提交 `b607e27`。
- 已把归档脚本 `git add` 范围收窄到 `工程记录/<project-name>`，记录为 TASK-009；已用修复后的脚本重新归档并推送 `2169d80`，知识库工作区干净。
- 记录时间：2026-08-16T18:05:00+08:00。


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


## 2026-08-16 拉取远端更新并同步安装到本地框架

- 远端更新：`2b5a553..32dbb4c`，含 `a-project-init` skill、docs/USAGE.md、全局 Agent turn-completion 纪律、project-log 归档修复等 6 个提交。
- 拉取：直连 fetch 失败（curl 56 连接重置），走 `127.0.0.1:10808` 代理成功；fast-forward 合并，工作区干净。
- 同步安装：`global_installer.py update` 成功，安装到 `C:\Users\12187\.codex`，备份 `backups\vibe-global-update-20260816-215024-213681`。
- 验证：`a-project-init/SKILL.md` 已安装；全局 AGENTS.md 已含“回合执行纪律”；`codex exec` 输出 `hook: SessionStart Completed`。
- 注意：安装器会重写 config.toml 的 `commandWindows` 为带引号形式，Windows 适配需在 update 后重新应用（本次已重新去引号并清除 trusted_hash）。


## 2026-08-16 SessionStart Hook 复发根因：cc-switch 重写 config.toml

- 现象：用户切换模型（cc-switch）后 SessionStart hook 再次 `hook exited with code 1`。
- 根因一（结构损坏）：cc-switch 用通用配置重写 config.toml 时把 `[[hooks.PostToolUse]]` 与 `[[hooks.PostToolUse.hooks]]` 之间插入 `[model_providers]`、`[mcp_servers.codegraph]` 等表，TOML 结构交错损坏；同时丢失 `[projects]`、`[windows]` 段。
- 根因二（引号回退）：cc-switch 通用配置模板 `cc-switch-common-config-codex.txt` 由 `scripts/generate_cc_switch_config.py` 生成，其中 `commandWindows` 为带引号形式；Windows 上 Codex 0.147.0+ 不解析引号，hook 无法启动。
- 修复（本地 + 源码生成器/安装器）：
  - 重建本地 `~/.codex/config.toml` 为合法 TOML（hooks 块连续、保留 projects/windows、commandWindows 无引号）。
  - `scripts/generate_cc_switch_config.py`：`hook_commands()` 的 windows_command 改为无引号；重新生成模板。
  - `scripts/global_installer.py`：`managed_config_block()` 的 windows_command 改为无引号，避免下次 install/update 回退。
  - `tests/test_installer.py`：同步断言 commandWindows 为无引号前缀。
- 验证：本地 config TOML 解析通过；`codex exec --dangerously-bypass-hook-trust` 输出 `hook: SessionStart Completed`；安装器测试 10 passed 1 skipped；临时 CODEX_HOME 完整安装生成的 commandWindows 为无引号。
- 说明：unix `command` 保持带引号，Linux/macOS 不受影响；Windows 上如果路径含空格需保留引号或用短路径。
