# 四项框架优化：技术选型与实现建议

日期：2026-09-19。关联：TASK-012 / RES-001 / DEC-006。
状态：研究交付；推荐尚未批准迁移，运行时尚未实现；策略为 spike-first。

## 1. 范围与约束

目标：恢复可信、记录一次、入口任务分流、证据版本适用性。
输入：用户两份复盘、D:/Project/my_lunwen 的只读核查、当前框架源码与一手技术资料。
本轮只修改本框架研究和进度记录；不修改论文项目、全局安装、运行时代码、Skills 或模型配置。
保留 Python 3.11+、Windows PowerShell 和 Linux；本机解释器为 vibe-python 指向的 Conda Python 3.11.15，sqlite3 可导入，SQLite 3.53.2。这只是环境可用性核查，不是事务/性能验证。
不引入服务端数据库、常驻服务、消息队列、ORM 或另一套 Agent 编排框架。不要求新订阅或外部推理调用。
Git 跨机器、分支切换和可读历史是约束；不能通过忽略同步问题来简化本机数据库设计。
小任务的控制开销必须可测；不把正文与实验的耗时算成框架优化收益。

## 2. 已有事实与待验证项

- 当前源码 run_git 使用 text=True，version_binding 将 diff 解码再编码；二进制输出应与显示文本分离。
- invalidate_evidence 按 covers.files 路径交集失效；PostToolUse 每次记录 work-unit-finished。
- 已有 atomic_write_text、file_lock、JSON Schema、argparse、unittest、vibe.py 与 loopctl.py，可复用而非重写全部。
- 现有 loop-active-run schema 已允许 waiting-user/blocked；缺陷主要是跨对象转换和校验没有落实，不能把修复简化为新增一个状态枚举。
- my_lunwen 实查：39 任务、69 证据（30 valid / 39 stale）、2567 事件；2304 个 work-unit-finished，2045 个没有变化路径；没有 review-completed 事件。
- TASK-030 被 Q-021 阻塞，但 Run 为 active、next_action 为空；Run.goal_id 为空，handoff 却展示已完成 GOAL-001。旧 Goal 明确不涵盖后续正文与最终图表。
- 30 条 valid 证据中 27 条至少一个文件绑定不匹配：10 条仅 CRLF/LF，3 条仅路径缺失，14 条有其他差异（其中 5 条也含换行差异）。这不是 27 条历史测试失败。
- EV-069 的三个源文件经 CRLF→LF 后全部匹配；EV-065/066 的旧 PDF 哈希不等于当前 PDF。证据既可能误失效，也可能漏失效。
- 事件无 changed_paths 不证明没有写入；工具名 Bash 不证明实际使用 WSL；缺少耗时原始数据，不能确认报告中的百分比分配。
- 本轮未执行新存储原型、故障注入、跨系统构建或吞吐基准；下述时延和字节预算均为试验目标。

## 3. 技术比较与选择

### 3.1 状态存储：SQLite 条件推荐，单文档文件存储保留为候选

| 候选 | 优点与匹配 | 成本/失败边界 | 结论 |
|---|---|---|---|
| 现有多 YAML + 增加写脚本 | 改动小，原格式/Git 兼容 | 单文件原子写不保证跨文件提交；仍需协调状态和失败恢复 | 只作过渡适配，不作为最终并行事实源 |
| 单个权威 state.json + 项目锁 + 原子替换 | 小规模足够；可直接 Git diff；统一事务可落为单次替换 | 整体解析/重写；跨分支内容冲突；锁恢复、revision 冲突处理需自管 | 若直接编辑/合并文本状态是硬约束，优先试验此候选；不能谎称必须上数据库 |
| Python sqlite3 + SQLite + 文本快照 | 利用事务、唯一键、外键、查询和备份；避免自制多文件事务 [S1,S2,S3] | 数据库不适合文本合并；需要显式 Git 快照进出、分支冲突策略；本机仍是单写者 | 首选原型，用户批准且通过同步试验后才迁移 |
| JSONL 全量事件溯源 | 追加记录、重放历史清晰 | 重放、事件版本迁移、并发顺序、快照维护会成为新的框架负担 | 不作为本轮主架构；保留事务内审计事件即可 |

SQLite 的选择理由是事务一致性和可查询性，不是当前 100 KB 文件已超出文件系统能力。官方将其定位为本地应用存储，并明确指出单写者和网络文件系统边界 [S1,S2]。sqlite3 属于 Python 标准库；SQLite 核心为 public domain [S3,S4]。不锁死本机 3.53.2 或引入新 ORM；在 Python 3.11 的实际发行环境做兼容矩阵。
建议先用默认回滚日志模式、短事务与有限 busy timeout；不要为尚未测量的并发收益默认启用 WAL。WAL 有同机共享内存与额外文件约束 [S5]。数据库不得放在多机同时打开的网络共享路径。
若 Git 快照流程比单文档状态带来更大日常开销，或用户要求直接在分支中人工编辑/合并全部机器状态，则放弃 SQLite 默认方案，选择单文档存储，仍保留相同业务命令边界。尚不承诺哪种方案实际更快。

### 3.2 其他选型

- 状态机：普通 Python 纯函数 + 显式转换表 + 现有 JSON Schema；不引入通用工作流引擎。状态语义属于本项目，适合小型自有实现。
- CLI：复用 argparse 和已有 vibe.py，loopctl.py 作为兼容适配器，不新增第二套状态写入逻辑。
- 摘要：固定字段渲染器，暂不加模板引擎；长研究文档仍是用户/Agent 编辑的内容，不从摘要反推需求。
- 分流：规则表 + Agent 提供结构化事实 + 运行时保守校验；不加独立 LLM 分类服务。
- 证据：hashlib + 文件/JSON 字段选择器 + 依赖边表；借鉴 DVC 的输入、命令、输出关系，不将 DVC 强制安装到每个文档项目。DVC 官方提供数据/模型版本和受影响阶段重跑能力 [S8]，但不能直接代替 Goal/Task 状态与评审语义。
- 后续项目已用 DVC 时，只引用其阶段结果和输入指纹，不接管其数据缓存/remote；版本、插件与许可在实际接入时另行核验。
- 依赖只沿用现有 PyYAML/jsonschema，加标准库 sqlite3/hashlib/pathlib；核心开源组件不新增付费服务。新写业务代码遵循仓库现有许可，不修改许可策略。

## 4. 恢复可信：明确对象职责，先检查再续跑

### 4.1 权威对象

- Goal：某次交付的成功条件与范围；可以有多个历史 Goal，不使用一个全局文件隐式代表所有后续工作。
- Task：一次可验证工作，goal_id 可空；小任务无须捏造宏大 Goal。scope/acceptance 和阻塞事实必须明确。
- Run：某个执行上下文对任务的推进，必须显式 task_id/goal_id；无 Goal 就显示无绑定，不从历史 Goal 文件兜底。
- Requirement 与 Goal 使用不同类型/ID；不能把 REQ-002 当作 Goal 外键。
- workflow 当前任务阶段/项目里程碑是不同字段；由选中上下文生成展示，不直接把所有阶段改成 completed。
- Native Goal 是可选外部绑定，未绑定不等于任务错误，也不自动创建线程 Goal；本框架状态不控制原生线程预算/执行。

建议表：goals、tasks、runs、blockers、evidence、evidence_inputs、reviews、domain_events、command_receipts、meta；必要的 notes 和 projection_jobs 存在同一数据库内。任务详细说明可用 JSON 字段，但关联 ID、状态、revision 和查询索引应为明确列。

### 4.2 必须保持的不变量

1. running Run 必须绑定存在且可执行的 Task；Task waiting-user/blocked 时，对应执行中的 Run 不得继续 running。
2. waiting-user 必须含 question_id、事实需求和恢复条件；blocked 必须含环境/依赖阻塞及解除条件；不得默认都变成用户等待。
3. blocked Task 不阻止独立的新任务启动；恢复应返回阻塞项与其他可执行工作，不能让项目永久卡在一个问题上。
4. Task done 需要所选策略要求的验收和当前适用证据；严格任务需要独立 review。完成 Task 同事务关闭相应 Run。
5. Goal 完成先检查该 Goal 范围内未结束任务/Run；未解决时拒绝完成，不能自动把任务标完成。新工作不得隐式借用 completed Goal。
6. 切换任务先暂停/交接旧 Run，或显式创建新的工作上下文；不覆盖没有保存的旧 Run。
7. 有待执行/待解除事项就必须有结构化 next_action；确实空闲或完成时允许空值，但摘要明确 idle/complete。

生命周期示意：Task pending → running → waiting-user/blocked → running → done；允许 cancelled；Run 对应 running/waiting-user/blocked/handed-off/completed/cancelled。最终枚举与旧 schema 的映射在迁移设计中冻结，不在本轮直接添加字段。
任务转换是纯函数：旧状态 + 命令 + 验收策略 → 新状态或结构化错误；跨对象变更在一个存储事务提交。DB 约束处理外键/唯一性，转换器处理跨对象业务条件，两者不可互相替代。

### 4.3 恢复与案例

restore 默认只读：查询当前上下文及相关 blockers，检查一致性，给出 next_action；发现冲突返回 state_conflict，不自动改业务事实、不假装可续跑。
repair --dry-run 产生可审阅修复计划；repair --apply 需要 expected_revision，不能按文件修改时间猜哪份摘要正确。
my_lunwen 应显示 TASK-030 等待 Q-021、旧 GOAL-001 是历史完成、论文当前 Goal 未明确绑定；是否新建论文 Goal 是显式决策，不由导入器推断。

## 5. 记录一次：命令服务、事务、自动投影

### 5.1 提议接口（尚不存在，不是可立即执行的命令）

    vibe context --task TASK-036 --format json --limit-bytes 8192
    vibe task begin --request request.json
    vibe task finish --request finish.json
    vibe task block --request block.json
    vibe state validate
    vibe state export
    vibe state import --dry-run
    vibe views refresh

request 文件也可改用 UTF-8 stdin；避免在 PowerShell/Bash 命令行拼大段 JSON。退出码区分无效输入、状态冲突、验证不通过与环境失败。
每个写命令包含 command_id、expected_revision、task/context、操作内容。finish 一次提交摘要、实际改动范围和验证结果；与其配套的任务/Run/事件/投影请求一起更新，不让 Agent 再编辑六个文件。

### 5.2 事务与故障协议

1. 事务外解析参数、计算输入指纹/执行验证；禁止持有数据库写锁等待编译或模型调用。
2. 开启短 BEGIN IMMEDIATE 事务，先查 command_id；已处理且载荷哈希一致则返回原结果，不一致报冲突。
3. 检查 expected_revision 和当前任务状态；转换器验证后更新所有相关实体、domain_event 和 command_receipt，增加 revision，写入投影任务，同一事务提交。[S2]
4. 提交后同步生成 Markdown/JSON 快照：失败只记录 projection_pending，不回滚已经成功的业务操作，也不重复登记证据。
5. 同 command_id 重试返回已提交结果并可重试投影；数据库 busy 采用有限等待，超时明确返回，不无限循环。
6. 验证期间输入有变化则结果不得标 current；在登记与完成门禁再次核查关键输入，检测到变动返回 needs-recheck。外部文件不在 SQLite 事务内，不能宣称跨文件验证是严格原子的。

current-session、progress、handoff 是可重建视图：带 source_of_truth、source_revision 和 generated_at；用户备注另存 notes，受管摘要不双向回写。
current-session 默认当前状态+最近 3 条，progress 默认最近 20 条；具体预算试用调整。机器 restore 不依赖这些 Markdown 是否及时生成。
多文件视图不能保证一起原子替换；逐文件原子替换后最后发布 revision/哈希 manifest，读者发现混合 revision 就重建或读取权威状态，不把半生成快照当完整快照。
工具诊断单独放本机 logs，默认关闭详细载荷或限量保留；domain_events 只记录任务转换、阻塞、证据判定、review 等有业务意义的事件。日志脱敏，不能存 token 或完整环境变量。

### 5.3 Git 与跨机器：SQLite 推荐的必要条件

- 本机 state.sqlite 和 journal 为不跟踪的运行数据；文本交换快照是跨机器传输载体，不是第二套可随意编辑的权威状态。
- 导出按任务/Goal/证据 ID 分文件并生成 manifest：project_id、schema_version、snapshot_id（内容摘要）、parent_snapshot_ids、文件哈希。revision 仅本机有序，不能用两台机器的整数大小判断谁更新。
- export 在一致读事务中获取数据；默认写操作完成后同步投影/导出，失败提示 pending。若导出未完成，必须明确“本机已保存、Git 交换副本未更新”。不能承诺自动防止任意外部 git push；框架交接/归档命令检查 pending，Git hook 集成须显式安装。
- 初始化克隆可从完整 manifest 导入；已有数据库与导出基线一致时可导入远端新快照。若本地也有未交换变更、未知项目 ID 或双分支冲突，停止导入并保留双方备份，不 last-write-wins。
- 独立实体合并也需要通过引用与状态不变量检查；同一任务状态的分歧要求显式 reconcile，不让模型自动决定是否完成。
- 分支/worktree 切换后，先核对基线 snapshot 和工作上下文；旧分支状态未保存就禁止自动覆盖。原型必须包含分支 A→B→A 与两台副本导出/导入测试。
- 数据库运行恢复以 DB 为准，交换时以显式导入事务为边界；旧 YAML 不再同步参与写入。快照仍是导出数据，人工修改只有经过 import 验证才成为状态。
- 默认不实现通用多主同步系统。如用户必须无感并行分支合并机器状态，此方案的成本假设失效，应重新选择文本权威存储。

## 6. 入口分流：先选负担，再加载上下文

先读取安全/项目约束与小型当前状态，识别是咨询、只读检查还是修改；不为了分类先加载整个 .project-log。
咨询默认不创建工程 Run；本轮研究因为明确交付方案才创建 research Task。快速修改仍有一个轻量事务记录，不经过完整生命周期。

| 路径 | 条件 | 记录与验证 |
|---|---|---|
| quick | 意图明确、局部可逆、无关键语义/数据/接口影响 | begin/finish 两次业务命令，单个精简任务、针对性验证、自动短摘要；不强制决策、架构、trace、Goal 和独立评审 |
| standard | 普通实现/缺陷修复，影响范围明确 | task + 变更概要 + 相关测试 + 必要证据，不重复抄写结果 |
| strict | 数据结论、安全权限、公开接口、发布/投稿关键规范等 | 明确验收、输入依赖、相关完整验证、真实独立 review |

Agent 提供风险事实，确定性规则计算最低等级；分类输出 reason_codes、required_checks、allowed_scope、escalation_triggers 与 policy_version。
信息不足不会自动全部 strict：一般未知选 standard 并标 unknown；可能涉及关键语义的未知先问最高影响问题。分类是辅助，不能证明 Agent 对风险的理解一定正确。
执行前后对照实际变化：触及未声明范围、关键保护路径或验收语义则暂停/升级；仅因想多写记录或“保险起见”不得升级。按风险而非行数分流。
TASK-036 需判断缩写变更是否影响术语语义/投稿约束；TASK-038 影响正式参考文献规范，建议 strict，但 strict 也只运行相关检查；highlights 未受影响且输入/工具指纹匹配时可复用其验证。
context 按 task→Goal/需求/阻塞/决策/证据引用查询，默认 8 KiB 是拟议输出预算；强制安全约束和阻塞信息不静默截断，必要时超预算并提示，其他内容按 ID 展开。

## 7. 证据：历史结果与当前适用性拆开

### 7.1 数据模型

- result：passed / failed / inconclusive；记录当时验证结果，不因后来修改而擦掉。
- applicability：current / stale / missing / unknown / historical；相对指定目标版本/工作上下文计算，不使用一个全局 valid 表达所有分支。
- identity：evidence_id、task/acceptance_id、验证主体、命令参数/工作目录、工具与校验器版本、所需环境指纹、检查时间。
- scope：输入 selectors、依赖 evidence IDs、输出 artifacts、hash_policy 及其版本。
- binding：每个输入 raw_sha256，以及明确启用的 content_sha256；保存未提交/未跟踪输入清单，git commit/diff 仅作背景，不能替代文件绑定。
- review：独立执行主体、被审版本指纹、意见与覆盖验收项；同一 Agent 切角色是降级复核，不等于独立 review。版本变更后重新判定 review 适用性。

Gate 只接受 passed + 对目标版本 current + 覆盖对应验收的证据；历史 passed 可查，但不替当前版本背书。缺失文件不直接判历史实验失败。
一个 Goal 的历史完成快照不因后续不相关任务追加而失效；重开/新交付要重新评估当前适用性。

### 7.2 指纹与选择器：先可证明的精度，后语义范围

第一版提供 raw-file、text-lf、json-pointer（连同 parser/selector version）。
raw-file 对 PDF、图像、模型、编码未知文件按原始 bytes 哈希。
text-lf 必须显式声明文本格式和换行非语义；只规范 CRLF→LF，不删除空白/注释，不归一化数学符号或 Unicode，不改变文件本身。保留 raw hash 以便字节级重现。[S6]
json-pointer 按字段/对象稳定序列化，保留数值类型、数组顺序并明确解析规则；数学精度敏感数据先保守用原始文件。
Git diff 用 bytes 哈希，不 strip、不 text=True，不在哈希前 decode/encode；人读错误信息另行容错解码。subprocess 原生支持二进制管道 [S7]。空 diff 与 git 执行失败必须分开，非 Git 项目可只用文件指纹并明确缺少提交背景。
语义范围第二步才加：显式区块 ID、指定指标集合/图表输入；不采用不稳定行号，也不让 LLM 判断“看起来不影响”。LaTeX 宏、include、前言和渲染全局布局会形成隐式依赖，定位失败或依赖不完整返回 unknown/整文件回退。

示例依赖：

    数据+计算代码+参数 → 指标验证 → 图表生成验证
    tex+bib+bst+图表+宏包/编译器 → 编译/引用/布局验证
    PDF_A+PDF_B → 文件同步验证

修改图注可以保留数据指标验证，却应重查渲染/分页。两份 PDF hash 相同只证明副本一致，不能证明正文、数据或版式正确。
临时 build/log 仅是产物或诊断，不默认作为所有输入依赖；正式交付 PDF 仍需要原始字节身份，不能为了消除噪声忽略其变化。

### 7.3 精确失效与漏检兜底

Hook 只提供可能变化的路径提示；候选证据重新比较 scope 指纹后才失效。只读工具不写业务事件；不能因工具叫 exec 就认定它写了文件。
用输入→证据的反向索引找到候选，变化只沿依赖边传播；纯读范围不产生失效。DAG 检测循环，依赖缺失返回 unknown。
Shell、手工编辑、Git checkout 可能绕过 Hook：任务 finish、review 与 Goal gate 必须独立核查本次所需输入；恢复仅检查当前任务依赖，不扫描全库所有模型/PDF。
mtime/size 仅作加速提示，不能作为完成门禁的充分证据。文件验证期间变化需检测重试或 unknown。
旧 valid 导入成历史结果，并重新计算适用性；旧字段未明确测试结果时不能凭 valid 推断 passed。CRLF 证据可识别差异类型，但未经声明文本策略不能批量自动豁免；找不到旧文件要区分可由 Git 恢复与未归档产物。

## 8. Windows/Linux 入口

提供薄 vibe.ps1 与 Unix 启动器：读取 CODEX_HOME/vibe-python、检查解释器存在与版本，再转发参数到同一 Python CLI。不通过 WSL 兜底，也不静默换解释器。
首次安装没有 vibe-python 时沿用 Conda bootstrap，但 Windows 启动 bootstrap 不能先依赖不存在的 py；安装器需有可检测的 bootstrap 解释器或明确失败说明。现有 install.ps1 的 py -3 入口应进入回归测试。
Python 子进程用参数数组与 shell=False，避免字符串拼接路径 [S7]；PowerShell 使用调用运算符转发数组参数；Windows PowerShell 5.1 与 PowerShell 7 都纳入测试，不能只测无空格路径。
JSON 输入/输出明确 UTF-8，Git 原始输出始终 bytes；中文路径、数学字符、空格、引号、LF/CRLF、无 py/python3、失效 vibe-python 都要有测试。
安装更新要同时迁移全局规则与 Skills 的入口指令，否则模型仍被旧提示要求读全量日志/调用旧解释器。此步骤需显式授权，不属于本轮研究。

## 9. 实现批次与退出条件

| 批次 | 具体交付 | 验收与退出 |
|---|---|---|
| A 正确性止血 | bytes Git 绑定、明确解释器、只读一致性诊断，不自动修复业务事实 | 非 UTF-8 diff 不崩溃；TASK-030 类矛盾有结构化告警；Windows/Linux 各自 smoke |
| B 最小事务原型 | StateStore 接口、单文档与 SQLite 对照、task begin/block/finish、幂等、投影恢复、Git roundtrip | 异常中断无半状态；并发不丢更新；相同命令只生效一次；双副本/分支冲突不静默覆盖 |
| C 低成本路径 | quick/standard/strict、任务上下文包、受管自动摘要、旧命令适配 | 小改动只需 begin/finish；不创建无关决策/架构；验收相关验证仍存在 |
| D 证据可靠性 | 历史/当前拆分、raw/text/JSON selectors、反向依赖、完成门禁重新核查 | CRLF 案例可解释；旧 PDF 不充当当前证据；手工修改被门禁发现；图注变化不误伤计算证据 |
| E 隔离迁移与发布 | 旧 YAML 导入预览、冲突报告、备份、快照同步、规则与安装器更新 | 在匿名化/最小复制案例与 Windows/Linux 临时项目通过；用户批准才部署实际项目 |

批次 B 未通过，不启动实际 SQLite 迁移；单文档存储是明确替代，不自动长期维护两个写后端。
代码落点建议：runtime/scripts 下状态服务/存储/转换/投影/证据策略模块；现有 vibe.py/loopctl.py 和 hooks 仅做适配。模块数量按最小垂直切片拆，不先建一大套空目录。
测试复用 unittest；先增加最小失败样本，不复制整份论文或含真实身份的材料进框架仓库。Python/Linux CI 与实际 Windows PowerShell 都需证据；本机没有 Linux 执行证据时标未验证。

## 10. 拟议验收矩阵（未执行）

1. block TASK-030 的事务同时更新 Run 和 next_action；Q-021 未解答时 finish 被拒绝，但独立任务可启动。
2. completed Goal 的新任务绑定被拒绝或要求明确新 Goal/独立任务；handoff 不展示无关旧 Goal。
3. finish 同 command_id 重试十次只产生一个结果；载荷变化拒绝；两个写者用旧 revision 竞争，一个明确冲突。
4. 强杀发生在 DB 提交前、提交后投影前、manifest 发布前：权威状态分别回滚或保留；视图可恢复，无伪完成和重复证据。
5. SQLite/单文档基准分别测 40/400/4000 tasks、70/700/7000 evidence，报告冷/热 p50/p95、调用数和读取字节；不提前宣传速度倍数。
6. 日常 context 初始预算 8 KiB，超限保留阻塞/安全约束并按 ID 分页；不读取全部 events 来给出当前任务。
7. 克隆导入、两个副本修改同一任务、分支 A→B→A、未导出写入时切分支：均不丢状态、不 last-write-wins。
8. bytes diff 含 GBK/非法 UTF-8/中文路径/二进制补丁仍可登记；Git 错误不得伪装为干净 diff。
9. EV-069 类 CRLF 差异保留原始 hash 且能解释内容等价；PDF 原始字节变化不会被文本规则掩盖。
10. 图注变更仅触发相关渲染/布局，计算结果依赖未变则继续 current；selector 丢失/命中多个位置时保守 unknown。
11. Strict review 绑定执行主体和被审版本；同实现者自审不满足独立门禁；外部 reviewer 不可用时明确降级并等待授权。
12. 只读查询不触发业务写事件；诊断日志有保留上限和脱敏；只读工具开销与业务写入数量分别统计。

## 11. 迁移、回滚与尚需批准的决定

导入是显式命令，不在 SessionStart 偷跑；先备份原记录并做 dry-run，列出未知关联、矛盾状态、缺失证据与解析错误。保留全部原 ID 和源文件定位；冲突不按“mtime 最新”自动裁决。
旧 schema 转换没有等价表示时保留 legacy_payload/provenance 并报告，不丢字段、不伪造 reviewer 或补写过去的通过结果。
启用新后端后旧工具必须只读或适配到统一服务，不能继续直接改旧 YAML。发布需包含 runtime、Hooks、Skills 和校验器版本兼容检查，旧写者遇新格式拒绝写入。
回滚分两类：切换前可恢复旧安装与备份；切换后已经产生的新写入必须先导出并验证可逆映射，不能直接覆盖旧备份丢掉新工作。无法降级表示则保留数据库和交换快照、只读旧视图，报告不能无损回退。
数据库备份使用标准 sqlite3 备份能力或关闭连接后的明确一致快照，不复制正在运行的数据库及不完整 journal。[S3]
待用户确认的 C 级选择：是否接受“机器状态通过 CLI/本机 SQLite 管理，Git 传递可读交换快照”，而非继续直接编辑/合并机器 YAML。此确认不等于批准自动迁移所有项目。
即使同意，仍先完成批次 B；若同步成本不合适则回到单文档候选。本轮只推荐，不将存储方案标为已批准。

## 12. 来源与置信度

检索日期：2026-09-19。网络检索工具未返回可用正文，改用可用 MCP 抓取以下官方文档；DVC 文档页连接重置后读取官方仓库 README。只发送公开资料地址，未上传项目内容。

- S1 SQLite 官方 Appropriate Uses For SQLite：`https://www.sqlite.org/whentouse.html`。本地应用文件、并发与网络文件系统限制。
- S2 SQLite 官方 Transaction：`https://www.sqlite.org/lang_transaction.html`。显式事务、BEGIN IMMEDIATE、busy、rollback。
- S3 Python 3.11 官方 sqlite3：`https://docs.python.org/3.11/library/sqlite3.html`。标准库接口与事务。备份能力应在原型阶段实际验证。
- S4 SQLite 官方 Copyright：`https://www.sqlite.org/copyright.html`。核心 public-domain 声明；未据此扩展判断其他依赖许可。
- S5 SQLite 官方 Write-Ahead Logging：`https://www.sqlite.org/wal.html`。WAL 与默认回滚日志、同机限制和额外文件。
- S6 Git 官方 gitattributes：`https://git-scm.com/docs/gitattributes`。text/eol/core.autocrlf 与工作树换行转换。
- S7 Python 3.11 官方 subprocess：`https://docs.python.org/3.11/library/subprocess.html`。默认二进制管道、文本转换和参数数组。
- S8 DVC 官方仓库 README：`https://raw.githubusercontent.com/iterative/dvc/main/README.rst`。依赖/命令/输出和数据版本工作流；仅参考设计，不新增 DVC 依赖。
- L1 当前源码：runtime/scripts/loop_state.py、loopctl.py、vibe.py；runtime/hooks/post_tool_use.py、hook_common.py；install.ps1。
- L2 真实案例：D:/Project/my_lunwen/.project-log 内 tasks/task-list.yaml、loop/evidence-index.yaml、loop/active-run.yaml、loop/handoff.md、goals/active-goal.yaml、workflow.yaml、retrospective/retrospective.yaml。

高置信：现有状态与指纹问题、标准库具备所需基础能力。中等置信：SQLite+统一命令服务能减少本机协调成本。待验证：相对单文档方案的总维护收益、Git 同步成本、延迟预算、selector 覆盖正确性与跨系统行为。
