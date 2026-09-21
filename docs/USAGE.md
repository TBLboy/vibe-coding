# Vibe Coding 用户使用指南

Vibe Coding 是一套面向 Codex CLI、VS Code 插件、桌面端和 ACP 外部协议连接端的**用户级全局工程工作流**。

它不只是给 Agent 增加几条提示词，也不只是一个安装脚本。它把一次开发工作串成一条可恢复、可验证、可追溯的链路：

```text
用户意图
  → 业务逻辑澄清
  → 需求基线
  → 技术研究与架构决策
  → 任务拆解与工程说明
  → 实现
  → 验证
  → 业务/代码/测试对齐
  → 复盘与经验沉淀
```

本文是面向日常使用者的完整指南。安装器参数和 AI 自动安装流程请分别参考：

- [README.md](../README.md)：项目概览、安装器参数和发布信息。
- [AI_INSTALL.md](../AI_INSTALL.md)：交给 AI 执行安装时的严格步骤。
- [AI_UPGRADE.md](../AI_UPGRADE.md)：升级、冲突处理、回滚和保留本地修改。
- [docs/EXTRACTION.md](EXTRACTION.md)：框架核心能力的提取边界。

---

## 1. 先理解三个层次

使用 Vibe Coding 时，最容易混淆的是“全局框架”和“当前项目”不是同一层。

### 1.1 全局安装层

全局安装层位于用户目录，负责让多个项目共享同一套 Agent 规则、Skills、Hooks 和 Loop 运行时，典型内容包括：

- 用户级 `AGENTS.md` 中的 Vibe 主 Agent 规则。
- `CODEX_HOME` 下的 Hooks、配置和备份。
- 用户级 Skills 目录。
- 全局 `vibe-coding` Python 环境及其路径记录。
- 可选 MCP 和本地插件配置。

更新全局层不会自动修改任意项目的业务代码，也不应删除项目中的 `.project-log/`。

### 1.2 项目记录层

每个接入 Vibe Coding 的项目根目录可以有一个 `.project-log/`，用来记录该项目自己的事实和过程：

```text
.project-log/
├── business-logic/       # 业务原子、澄清结论、开放问题
├── requirements/         # 需求基线
├── research/             # 技术方案研究
├── architecture/         # 架构决策
├── tasks/                # 任务清单与完成条件
├── specs/                # 工程说明
├── verification/         # 验证证据
├── alignment/            # 业务、代码、配置、测试对齐结果
├── decisions/            # A/B/C 决策记录
├── loop/                 # Loop 状态、事件、证据索引和 handoff
├── docs/                 # 项目日志说明与长文档归档（docs/archive/）
├── work-trace/           # 紧凑工作留痕
├── retrospective/        # 阶段复盘
└── distillation/         # 可沉淀的经验候选
```

项目日志是项目的持久记忆，不是聊天记录的复制品。它应记录确认事实、可复核证据、决策摘要和下一步，而不是把模型的隐性推理写进去。

`current-session.md` 和 `progress.md` 是面向人的长 Markdown 摘要，维护约定如下：

- **最新在最上**：最新会话区块或最新阶段段落位于文件顶部，旧内容依次向下。
- **头部快照**：顶部维护简短稳定的“当前状态”区块，每次更新时覆盖而不是追加，方便不翻页即可恢复。
- **超限归档**：`current-session.md` 超过约 50-100 KB 或会话区块达到约 10 条时，把旧区块移到 `docs/archive/`；`progress.md` 超过约 50-100 KB 时做同样处理。归档保留全部历史，不删除事实。
- **单一事实源**：精确当前状态和下一步以 `loop/active-run.yaml`、`loop/handoff.md` 为权威状态源；两个 md 摘要不得与之矛盾。机器维护的 `loop/` 与 `verification/evidence.yaml` 文件不要手工重排。

### 1.3 当前对话层

当前 Codex 对话负责执行一个有限工作单元。它可以被压缩、暂停、切换或重启，因此不能把聊天上下文当作唯一状态。

SessionStart 和 PreCompact Hook 会从项目日志恢复紧凑上下文。恢复只是让 Agent 重新获得事实状态，不代表任务已经完成；有未完成任务时，Agent 应继续执行具体下一步。

---

## 2. 安装前准备

### 2.1 基本环境

建议准备：

- 当前可用的 Codex 客户端。
- Python 3.11 或更高版本。
- Conda、Miniforge 或 Miniconda，用于创建统一的 `vibe-coding` 环境。
- 如需拉取可选 MCP 或访问 GitHub 远端，准备可用的网络代理。

默认代理地址是 `127.0.0.1:10808`，也可以通过环境变量调整：

```bash
export HTTP_PROXY=http://127.0.0.1:10808
export HTTPS_PROXY=http://127.0.0.1:10808
```

代理不可用时，核心安装仍可以完成；可选 MCP 的安装或远端同步可能失败，应把它作为环境限制单独记录，而不是阻塞核心工作流。

### 2.2 统一 Vibe Python

安装器、Hooks、`loopctl`、项目校验和包校验使用统一的用户级 Python。安装器会优先使用：

```text
${CODEX_HOME:-$HOME/.codex}/vibe-python
```

如果该文件不存在，包装脚本会尝试寻找 Conda/Miniforge/Miniconda，创建或修复名为 `vibe-coding` 的 Python 3.11 环境，并安装：

```text
runtime/scripts/requirements.txt
```

也可以临时指定解释器：

```bash
export VIBE_PYTHON=/absolute/path/to/python
```

不要在已经配置了 `vibe-python` 后随意使用系统 `python3` 执行 Loop 或 Project Log 工具，否则可能因为依赖版本不同产生难以复现的结果。项目自身的 Python 应用仍然使用项目自己的虚拟环境，不需要迁移到 `vibe-coding`。

### 2.3 安装方式

Linux/macOS：

```bash
chmod +x install.sh update.sh uninstall.sh
./install.sh
```

Windows PowerShell：

```powershell
.\install.ps1
```

默认安装行为：

- 保留现有 Codex 权限配置。
- 安装主 Agent、Skills、runtime 和三个低风险 Hooks。
- 自动创建带时间戳的备份。
- 新安装默认不启用可选 MCP。
- 不静默删除用户已有配置。

如需显式选择可选 MCP，可以重复指定 `--mcp`：

```bash
./install.sh --mcp codegraph
./install.sh --mcp codegraph --mcp vibe-toolbelt
```

受限网络下可以显式跳过可选 MCP：

```bash
./install.sh --without-mcp
```

安装完成后建议验证：

```bash
${CODEX_HOME:-$HOME/.codex}/vibe-workflow/scripts/loopctl.py --help
python scripts/global_installer.py verify
```

日常运行可使用平台原生入口，它会读取 `vibe-python`，不要求 PATH 中存在 `py` 或 `python3`。

Windows PowerShell：

```powershell
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
& (Join-Path $CodexHome 'vibe-workflow\vibe.ps1') --root (Get-Location).Path status
```

Linux/macOS Bash：

```bash
bash "${CODEX_HOME:-$HOME/.codex}/vibe-workflow/vibe.sh" --root "$PWD" status
```

入口也支持 `--codex-home <目录>` 或 `--codex-home=<目录>`。通过 `pwsh -File` 从外部程序启动时，请使用分开的 `--codex-home "D:\配置目录"`：已测试的 PowerShell 7.4.6 宿主会在脚本收到参数前拆开 `--codex-home=D:\配置目录` 中的盘符冒号。入口对这种歧义报错并提示分开传参，不猜测重组路径。直接在 PowerShell 内调用脚本的等号形式不受此限制。

解释器优先级为显式 `VIBE_PYTHON`、该目录的 `vibe-python`；配置必须是单行绝对可执行路径，Python 至少为 3.11。配置文件接受 UTF-8 BOM 与 CRLF，但不接受多条路径或相对路径。错误配置明确报错，不静默切换 PATH、WSL 或安装环境；子进程的文本输入输出明确使用 UTF-8。

首次安装与日常运行分开：仅安装入口可以通过 `VIBE_BOOTSTRAP_PYTHON` 或自动发现的兼容解释器启动现有 Conda 初始化流程。日常入口只运行已配置环境。Windows 入口保留空参数、引号与反斜杠；跨平台测试使用隔离配置目录，不更改用户实际安装。

直接调用校验脚本时，仍应使用 `vibe-python` 指向的解释器，例如：

```bash
PY="$(cat "${CODEX_HOME:-$HOME/.codex}/vibe-python")"
"$PY" runtime/scripts/validate_package.py --root .
```

> Windows 上如果 Codex 报告 Hook 启动失败，请参考 `AI_INSTALL.md` 的“Windows Hook 命令适配（Codex 0.147.0+）”。Linux/macOS 不需要该适配。

---

## 3. 第一次接入一个项目

在项目根目录打开 Codex，然后直接告诉 Agent：

```text
初始化这个工程
```

或：

```text
vibe 开始
```

Agent 应完成以下检查：

1. 确认项目根目录和 Git 状态。
2. 阅读项目现有 `AGENTS.md`、README、配置和测试入口。
3. 创建 `.project-log/`，或安全复用已有项目日志。
4. 建立或安全更新根目录 `AGENTS.md`。
5. 识别项目级规则、团队协作边界和不可随意修改的公共资源。
6. 报告初始化结果和后续需要用户确认的问题。

如果项目还没有 `AGENTS.md`，初始化流程会注入通用 Vibe 规则，并留下项目级规则区。如果已经有 `AGENTS.md`，通用区通过标记幂等注入，原有项目内容应保留。

### 3.1 个人仓库和团队仓库

初始化时要明确项目类型：

- **个人仓库**：Agent 可以在授权范围内直接推进低风险、可逆改动。
- **团队仓库**：涉及公共接口、执行器、部署配置、共享资源或多人正在使用的分支时，应先询问或建立明确边界。

不要把某个项目中的临时环境问题自动写成全局规则，也不要把代码当前的偶然行为直接升级为业务要求。

### 3.2 初始化后的快速检查

可以对 Agent 说：

```text
检查一下当前项目的 Vibe 状态
```

也可以手动运行：

```bash
PY="$(cat "${CODEX_HOME:-$HOME/.codex}/vibe-python")"
"$PY" runtime/scripts/validate_project.py --root .
"$PY" "$HOME/.codex/vibe-workflow/scripts/loopctl.py" --root . --json restore
"$PY" "$HOME/.codex/vibe-workflow/scripts/loopctl.py" --root . validate
```

新项目的预期结果是：Project Log schema 通过，Loop 状态可读取，且没有错误的 active task。

---

## 4. 一个完整任务应该怎样推进

下面以“为机器人项目新增设备状态采集”为例。你不需要一次性给出完美需求，应该让 Agent 通过澄清逐步建立事实基线。

### 4.1 先描述目标，不要直接指定实现

推荐：

```text
我想让机器人采集设备状态，并在设备异常时通知上层。请先不要写代码，先帮我澄清角色、状态、频率、异常和验收条件。
```

不推荐一开始就说：

```text
直接新增一个 ROS 2 节点，每 100ms 发布一个 topic。
```

后一句把技术方案误当成需求，可能掩盖了采集对象、异常语义、数据保留和兼容约束。

### 4.2 业务逻辑澄清

在澄清阶段，Agent 应分别检查三个维度：

#### 功能业务逻辑

系统应该如何表现：

- 谁使用或依赖这个能力。
- 哪些设备、状态和事件需要覆盖。
- 正常、降级、超时、断连、恢复分别如何处理。
- 数据是否需要去重、排序、保留历史或触发通知。
- 边界条件和业务不变量是什么。

#### 技术业务逻辑

当前系统实际上如何承载：

- 已有节点、消息、服务、数据库或配置入口。
- 现有线程、并发、时序和生命周期约束。
- 设备驱动、网络、权限和运行环境限制。
- 哪些接口是公共接口，哪些只是内部实现。

#### 双向对齐

比较“应该怎样”和“当前怎样”，并明确分类：

- 已匹配。
- 缺少实现。
- 缺少测试。
- 实现漂移。
- 测试漂移。
- 业务冲突。
- 尚未确认。

可以使用：

```text
进入业务逻辑澄清，分别检查功能业务逻辑、技术业务逻辑和双向对齐。
```

如果 Agent 发现现有代码与需求冲突，不应为了让测试通过而静默修改业务规则。

### 4.3 固化需求基线

当范围、边界、假设和未决问题已经足够清楚时，对 Agent 说：

```text
把当前澄清结果固化为需求基线，并列出未解决的问题。
```

需求基线至少应说明：

- 本次目标和非目标。
- 角色、场景和状态转换。
- 输入、输出、异常和边界。
- 兼容约束、数据约束和安全约束。
- 验收条件。
- 尚未解决的问题及其决策级别。

如果仍然存在会改变产品语义、公开接口、数据、安全、持续费用或不可逆架构的问题，Agent 应停在澄清或询问用户，而不是继续猜测。

### 4.4 技术研究、架构和任务拆解

需求明确后，可以连续使用：

```text
进入技术选型，比较成熟方案并给出推荐。
```

```text
根据已确认需求做架构决策，说明模块边界、接口、数据流和故障处理。
```

```text
把任务拆成依赖清晰、可独立验证的垂直切片。
```

```text
为当前任务写工程说明，包含改动文件、接口、迁移、回滚和测试。
```

技术方案研究应回答“为什么选它、替代方案是什么、风险是什么”，而不是只列出一个库名。架构记录应明确：

- 模块职责和边界。
- 输入输出与数据流。
- 失败、重试、超时和回滚策略。
- 并发、一致性和兼容性约束。
- 运行、监控和排障方式。

### 4.5 实现阶段

实现时，Agent 应按最小一致改动推进：

```text
开始实现已批准的 TASK-XXX，先运行现有检查，再按垂直切片修改并验证。
```

通常流程是：

1. 先运行相关现有测试，确认基线。
2. 修改最小范围的代码、配置或文档。
3. 为新行为增加针对性测试。
4. 每完成一个切片就运行最窄的验证。
5. 发现业务歧义时返回澄清，不用代码偷偷决定产品语义。
6. 记录变更、偏离、失败归因和下一步。

当任务足够明确且写入范围互不重叠时，Agent 可以委派受限子 Agent 进行只读探索、技术研究或独立复核；产品代码默认只允许一个实现 Agent 写入，最终集成和完成判断由主 Agent 负责。

### 4.6 验证阶段

实现完成不等于任务完成。可以说：

```text
按验收条件验证当前实现，给出每条条件的命令、结果、证据和限制。
```

验证应覆盖适用的方面：

- 正常路径。
- 异常和边界。
- 状态转换和副作用。
- 兼容性、迁移和回滚。
- 并发、重试、超时。
- 权限和安全。
- 运行环境限制。

证据状态包括：

- `candidate`：已记录但尚未确认。
- `valid`：当前版本下可复核且通过。
- `failed`：执行失败。
- `stale`：覆盖的代码、配置、需求或测试已变化。
- `superseded`：被新证据替代。
- `invalid`：证据本身不可用。

覆盖对象发生变化后，旧证据应变为 `stale`，不能删除旧证据来掩盖失效。

### 4.7 对齐、复盘和沉淀

实现后可以继续说：

```text
检查业务逻辑、代码、配置和测试是否双向对齐。
```

```text
对本次增量做复盘，区分决策、行动、结果、失败和返工原因。
```

```text
从重复出现且有证据支持的经验中提炼候选规则，但不要直接修改全局规则。
```

经验只有在重复证据和用户批准后，才适合固化为 Skill、模板、Agent 或全局规则。

---

## 5. 三套状态要分开看

### 5.1 Project Goal

Project Goal 保存在项目日志中，描述项目级目标、成功条件和必需证据。它是业务完成契约。

```text
Project Goal = 这个项目/增量要达到什么结果
```

没有 Project Goal 时，`loopctl evaluate goal` 会明确报告未定义，而不是假装完成。

### 5.2 Codex 原生 Goal

Codex 原生 `/goal` 负责当前线程的运行、暂停、恢复、预算和 continuation。它是线程控制器，不应被项目日志中的临时措辞替代。

```text
Native Goal = 当前 Codex 线程如何继续运行
```

Project Goal 和 Native Goal 可以绑定，但二者不能互相覆盖事实。

### 5.3 Vibe Loop 状态

Loop Core 记录阶段、任务、失败计数、证据有效性和 handoff。常见状态：

- `active`：有未完成工作，应继续具体下一步。
- `waiting-user`：等待用户回答或确认。
- `blocked`：被明确依赖或环境阻塞。
- `handed-off`：已生成交接信息，尚未继续。
- `complete`：该 run 已完成，不应作为 active work 恢复。

常用命令：

```bash
PY="$(cat "${CODEX_HOME:-$HOME/.codex}/vibe-python")"
LOOP="$HOME/.codex/vibe-workflow/scripts/loopctl.py"

"$PY" "$LOOP" --root . --json restore
"$PY" "$LOOP" --root . --json status
"$PY" "$LOOP" --root . validate
"$PY" "$LOOP" --root . handoff
```

通常用户不需要手工编辑 Loop YAML。遇到状态不一致时，优先让 Agent 读取事件、项目日志和当前任务，再决定是继续、handoff、回到上游阶段还是清理残留状态。

### 5.4 失败和重试

验证失败后，Agent 必须先分类失败来源：

- `implementation`：实现缺陷。
- `specification`：工程说明不足。
- `task-decomposition`：任务切片不合理。
- `technical-selection`：技术方案不合适。
- `functional-business-logic`：功能业务逻辑不清或错误。
- `technical-business-logic`：现有技术承载事实未对齐。
- `environment`：环境、权限、依赖或外部服务问题。
- `verification-harness`：测试或验证工具自身问题。
- `unknown`：暂时无法归因。

重试必须说明：

1. 可证伪的假设。
2. 相对上次的具体变化。
3. 预期获得的新证据。

失败签名和变化量都不变时，不应机械重复同一个操作。

---

## 6. 决策权限：哪些事情 Agent 可以直接做

### A 级：可逆、低风险、局部细节

Agent 通常可以直接决定，例如：

- 函数命名、局部文件组织和测试写法。
- 不改变行为的格式化和小范围文档措辞。
- 已有方案内的实现细节。

### B 级：可以自主决定，但需要留痕

Agent 可以推进，但应写入 `decision-log.yaml`，例如：

- 在多个等价技术实现中选择一个。
- 调整内部模块边界。
- 选择验证工具或兼容策略。

### C 级：先询问用户

以下事项不能静默决定：

- 改变产品语义、用户行为或业务范围。
- 修改公开接口、数据格式、数据迁移或安全策略。
- 引入持续费用、外部服务或新的权限。
- 不可逆的架构、仓库结构或部署选择。
- 覆盖团队公共资源或其他人的本地修改。

提问时 Agent 应只问影响最高的一个问题，并给出推荐选项与影响。

---

## 7. 多客户端使用规则

Vibe Coding 的规则和项目日志与接入端无关，以下客户端共享同一套生命周期：

- Codex CLI。
- VS Code 插件。
- Codex 桌面端。
- ACP 外部协议连接端。

可以在一个客户端初始化项目，在另一个客户端继续。前提是：

1. 使用同一个项目根目录。
2. 不要删除或手工覆盖 `.project-log/`。
3. 保持全局 `CODEX_HOME` 和 `vibe-python` 指向一致。
4. 切换客户端后先让 Agent 执行恢复或状态检查。
5. 不要同时让多个 Agent 修改同一个公共文件或同一个任务的写入范围。

多客户端并不意味着多个独立 Loop。项目日志是共享事实源，当前线程的 Native Goal 仍由各自 Codex 会话控制。

---

## 8. cc-switch 与可选 MCP

### 8.1 cc-switch 通用配置

如果使用 cc-switch 热切换 Codex 供应商，需要把当前宿主机生成的 Vibe TOML 段放入 cc-switch 的通用配置：

```bash
python scripts/generate_cc_switch_config.py --output cc-switch-common-config-codex.txt
```

然后用生成文件中以下标记之间的内容覆盖 cc-switch 通用配置中的对应段：

```text
# VIBE-CODEX-GLOBAL:CONFIG:BEGIN
...
# VIBE-CODEX-GLOBAL:CONFIG:END
```

注意：

- 生成结果包含绝对路径，**不能跨机器直接复制**。
- 更换宿主机后重新运行生成脚本。
- 热切换后建议重新启动 Codex 会话。
- 若安装器报告配置冲突，不要强行覆盖，先保留备份并比较三方配置。

### 8.2 可选 MCP

新安装默认只启用核心能力。可选 MCP 需要明确选择，并受网络、代理、Node/uvx/npm 或外部服务影响。

查看 catalog：

```bash
cat runtime/mcp/optional-mcps.json
```

选择 MCP：

```bash
./install.sh --mcp codegraph
```

验证配置：

```bash
codex mcp list
python scripts/global_installer.py verify
```

如果 MCP 安装失败，先确认：

- 代理是否可用。
- 外部命令是否存在。
- 当前 Codex 会话是否需要重启才能加载新配置。
- 核心 Hooks 和 Project Log 是否仍然正常。

MCP 是可选增强，不应阻塞没有 MCP 时的核心 Vibe 工作流。

---

## 9. 常见操作速查

### 开始一个新工作单元

```text
vibe 开始：我要实现……，先检查项目状态并拆分下一步。
```

### 恢复上次工作

```text
vibe 恢复当前项目，先读取 current-session、任务、证据和 Loop 状态。
```

### 只做规划，不写代码

```text
请先完成业务澄清、需求基线和任务拆解，暂时不要修改产品代码。
```

### 开始实现

```text
实现 TASK-XXX。严格按完成条件推进，先运行基线测试，每个切片完成后验证。
```

### 验证当前改动

```text
按验收条件验证，不要只报告测试通过；列出证据、限制和未验证项。
```

### 发现需求不清

```text
停止当前实现，回到业务澄清，只问一个影响最高的问题，并给出推荐答案。
```

### 检查代码与业务是否漂移

```text
执行业务/代码/配置/测试双向对齐，分类记录 missing-implementation、missing-test、implementation-drift、test-drift、traceability-gap 或 conflict。
```

### 结束或交接

```text
生成当前项目 handoff，写清已完成、未完成、验证证据和精确下一步。
```

### 归档工程

```text
帮我归档这个工程。
```

归档前应先完成当前阶段验证。归档 Skill 会把项目日志同步到用户指定的个人知识库；归档本身不应删除项目工作区中的 `.project-log/`。

---

## 10. 常见问题排查

### 10.1 Agent 只输出“已恢复状态”，没有继续工作

这是不完整的行为。恢复状态不是交付。可以明确要求：

```text
不要只汇报恢复摘要。根据记录中的 next action 继续执行；如果没有活动任务，就为我的新请求创建一个 run。
```

### 10.2 SessionStart 显示了旧任务

先运行：

```bash
PY="$(cat "${CODEX_HOME:-$HOME/.codex}/vibe-python")"
"$PY" "$HOME/.codex/vibe-workflow/scripts/loopctl.py" --root . --json restore
"$PY" "$HOME/.codex/vibe-workflow/scripts/loopctl.py" --root . validate
```

检查 `.project-log/loop/active-run.yaml`、`events.jsonl` 和 `handoff.md` 是否一致。不要直接删除事件；应保留清理或完成事件，使状态变化可追溯。

### 10.3 Project Log 校验失败

先区分：

- YAML 解析失败：检查缩进、冒号、特殊字符和未引用的字符串。
- schema 失败：检查必填字段、枚举值和字段类型。
- 引用失败：检查 task、decision、evidence 和 business logic ID 是否存在。
- Loop 失败：检查 active run 的最后事件、状态和计数器。

运行：

```bash
PY="$(cat "${CODEX_HOME:-$HOME/.codex}/vibe-python")"
"$PY" runtime/scripts/validate_project.py --root .
"$PY" "$HOME/.codex/vibe-workflow/scripts/loopctl.py" --root . validate
```

### 10.4 Windows Hook 失败

Codex 0.147.0 及更新版本在部分 Windows 环境下对 Hook 命令的引号解析方式发生变化。如果错误表现为 Hook 进程没有启动，而脚本直接运行正常，按 `AI_INSTALL.md` 中的 Windows 专用适配步骤检查 `commandWindows`；不要修改 Linux/macOS 的 `command`。

### 10.5 cc-switch 切换后 Hooks、插件或 marketplace 消失

这通常意味着 cc-switch 整写了 `config.toml`。处理顺序：

1. 保留当前配置和安装器备份。
2. 重新生成当前宿主机的 cc-switch 通用配置。
3. 确认 Vibe 标记块完整。
4. 运行安装器 update/verify。
5. 重启 Codex 会话。

不要把另一台机器生成的配置直接复制过来。

### 10.6 测试失败但代码可能没有问题

先判断失败来源：实现、需求、技术选择、环境还是验证工具。比如网络不可用导致 MCP 拉取失败，不应被记录为产品实现失败；测试夹具自身不兼容，也不能通过修改业务代码解决。

---

## 11. 安全边界和使用习惯

为了让工作流可控，建议坚持以下习惯：

- 先让 Agent 读现有规则、代码、配置和测试，再让它修改。
- 先说“不要写代码，先澄清”或“只做规划”，避免过早进入实现。
- 公开接口、数据、安全、费用、团队共享资源和不可逆动作先要求 Agent 提问。
- 不要把密码、Token、个人隐私或未脱敏生产数据写进提示、项目日志或证据。
- 不要把当前主机的绝对路径、临时代理和本地调试参数当成跨机器配置提交。
- 不要删除旧证据、事件或 `.project-log/` 来掩盖失败；应标记 stale、failed 或 superseded。
- 代码实现完成后必须单独验证；实现 Agent 不应成为自己的唯一 Reviewer。
- 没有验证证据时，状态应保持 `implemented-unverified`，而不是口头宣布完成。

---

## 12. 从项目日志中恢复工作

如果重新打开一个旧项目，推荐第一句话是：

```text
vibe 恢复。请读取项目根目录的 AGENTS.md、.project-log/current-session.md、workflow、任务清单、需求基线、决策、验证证据和 Loop 状态，然后继续执行精确下一步。
```

恢复后重点查看：

1. `current-session.md`：最近一次会话的结论和下一步。
2. `tasks/task-list.yaml`：任务状态和 `done_when`。
3. `loop/active-run.yaml`：当前阶段、任务、状态和计数器。
4. `loop/handoff.md`：压缩或暂停前的交接摘要。
5. `verification/evidence.yaml` 与 `loop/evidence-index.yaml`：证据是否仍然有效。
6. `business-logic/open-questions.yaml`：是否有未解决的 C 级问题。

如果状态已经是 `complete`，不要继续恢复旧 run；把用户的新请求作为新的任务，并先创建新的 run。

---

## 13. 完成标准

一个任务只有在以下条件都满足时，才应称为完成：

- 需求范围和业务规则已确认，或明确记录了限制。
- 代码、配置、文档和测试实现了同一份业务逻辑。
- `done_when` 中的完成条件逐项验证。
- 失败已归因，未把环境问题伪装成实现成功。
- 验证证据已登记，且覆盖对象没有变更导致 stale。
- 必要的独立 Review 已完成。
- `.project-log/`、Loop 状态和当前会话记录一致。
- 用户知道剩余限制、未验证项和下一步。

最终输出应包含：

```text
完成内容：...
验证命令与结果：...
证据：...
未验证项/限制：...
变更文件：...
精确下一步：...
```

这套工作流的目标不是让 Agent 写更多文字，而是让每个重要决定、实现和结论都能被恢复、质疑和验证。

## 14. 事务状态（format 2）与初始化

format 2 是框架的默认格式：新建项目直接生成新格式，不再需要实验开关。任何已有 `.project-log` 都不会被覆盖——初始化报告 `skipped` 并保持原样。存量旧格式项目在迁移窗口内继续可用，迁移路径见本节末尾。生产契约的冻结原文在框架仓库迁移后保存于 `.project-log/legacy/specs/framework-landing-contract.md`。

通过配置好的原生 `vibe.ps1` / `vibe.sh` 入口调用：

```text
--root <project> init
--root <project> status
--root <project> validate
--root <project> task begin|update|wait|resume|handoff|finish|cancel
--root <project> record create|update|link
--root <project> evidence record|invalidate|refresh
--root <project> review record
--root <project> gate --task TASK-001
--root <project> goal update|complete --id GOAL-001
--root <project> route --path <file> --signal <signal>
--root <project> context TASK-001 --budget-bytes 4096
--root <project> render
--root <project> migrate preview|apply|resume|rollback
--root <project> exchange status|export|import|finish|abandon
```

需要脚本化或批量写入时，仍可使用底层统一信封。`command.json` 是 UTF-8 JSON，而不是需要跨 Shell 转义的内联字符串：

```json
{
  "schema_version": 1,
  "command_id": "create-task-001",
  "expected_revision": 0,
  "action": "task.create",
  "payload": {"id": "TASK-001", "title": "隔离验证任务", "goal_id": null}
}
```

每个新的业务操作使用新的 `command_id` 和最近观察到的 `revision`。网络或调用中断后，重试原始信封（包括原始 revision），返回原回执；不能修改同一 ID 的载荷或 revision。`goal.create` 显式创建目标；任务不自动继承历史目标。等待用户必须记录问题引用和恢复条件。

新格式的结构化事实包括：

- `records` / `record_links`：业务原子、需求基线、决策、架构、研究、对齐、复盘与蒸馏及其交叉引用；
- `evidence`：证据状态、覆盖范围与产物哈希绑定；
- `reviews`：任务级独立复核、结论与证据引用。

长文档正文只放在 `.project-log/docs/**`，结构化记录只保存 `doc_ref`（路径与内容哈希）。`task.finish` 要求至少一条 `valid` 且覆盖该任务的证据；高风险任务还要求独立 `go` 复核。`goal.complete` 会逐条检查 `success_conditions`、`required_evidence` 与显式 `not-applicable` 理由。`evidence refresh` 会在覆盖文件字节变化后把证据写成 `stale`，旧证据不会被删除。

新格式标记为 `.project-log/state-format.json`。Git 项目数据库位于该 worktree 的 Git 管理目录下，按项目 ID 和分支上下文隔离；非 Git 测试项目位于 `.project-log/.state/`。不会把 SQLite 文件加入 Git。初次切换到没有本地状态的分支会明确失败，而不是沿用另一分支的状态。跨副本同步只在显式执行 `state-export`/`state-import` 时发生，见下文“显式快照交换”；日常任务命令不会触发同步。普通操作不占用或清理 `index.lock`。

自动摘要保存在数据库旁的 `generated` 目录。以 `CURRENT.json` 指向的同一版本为一组读取，校验项目、上下文、revision 和内容哈希；不逐文件猜测哪个版本更新。`current-session.md`、`progress.md` 和 `handoff.md` 是派生视图，不是另外三份事实源，也不覆盖项目中的同名用户笔记。投影失败时业务提交仍成立，返回 `projection: pending`，可用 `state-views` 修复，不需要再次登记业务操作。生成内容由 revision 唯一决定，因此生成目录里缺失的文件（含 `manifest.json`）会在下次 `state-views` 或 `state-export` 时原地补写，结果中的 `repaired` 列出补写的文件名；已存在但字节不同的文件属于篡改，仍然失败关闭（`projection_incomplete`），不会被静默覆盖。

新格式下，启动 Hook 与会话恢复从状态库读回目标、任务、阻塞、证据有效性与精确下一步；`PostToolUse` 只按记录哈希精确失效证据，不创建旧 YAML。旧写命令明确拒绝，并提示使用正式 `vibe` 入口。初始化中断、缺失数据库、无法识别的标记或遗留投影锁均需保留现场并调查；不要删除标记、数据库或锁来让旧入口接管。

`.project-log/.state/` 是新格式保留的本机所有权目录，Git 项目也保留此目录用于防止格式标记丢失后回退到旧写入器。目录仍在而标记缺失时（包括切换到不含标记的旧分支），入口保守拒绝恢复，不自动补写旧 YAML；需要后续显式迁移/交换流程处理，不能通过删除目录绕过。Hook 从子目录启动时会识别上层新格式项目，路径别名也不能绕过旧写入保护。

### 显式快照交换

跨副本同步只在显式执行时发生，日常任务命令永远不占用 Git index 锁。快照对象写入 `.project-log/exchange/`，随 Git 提交分发；它们按内容寻址、不可变，且标记为不转换行尾，因此在不同平台克隆之间字节稳定。

```text
--root <test-project> state-attach                      # 新克隆：为当前 worktree 建立本机状态库
--root <test-project> state-export                      # 发布本机状态为不可变快照
--root <test-project> state-import                      # 校验并导入当前 worktree 已发布的快照
--root <test-project> state-exchange                    # 只读查看本机/已发布版本、共同基线与待恢复状态
--root <test-project> state-exchange-finish             # 崩溃后确认待发布快照就是已写入的指针
--root <test-project> state-exchange-abandon --reason "..."   # 确认未发布后放弃待发布意图
```

典型流程：克隆 A 建立状态并 `state-export`，提交推送；克隆 B `state-attach` 后 `state-import` 取得 A 的状态；B 继续工作并 `state-export`；A 拉取后 `state-import` 取得 B 的新命令。两端各自的 `revision` 是本机提交序号，导入的历史命令保留原始分支上下文和原始 revision，因此本机序号与来源坐标不会互相污染。

导入只在下列条件全部成立时接受，否则明确拒绝且不改动任何状态：

- 快照摘要、指针与载荷哈希一致，且清单字段完整；
- 项目身份相同，快照确实从本机记录的共同基线派生（否则 `snapshot_diverged`）；
- 本机没有尚未发布的命令（否则 `unexported_changes`，两端版本都保留，不做覆盖式合并）；
- 双方共享命令的请求与回执字节完全一致（否则 `history_rewritten`）；
- 快照的实体表与其账本互相一致，不存在没有对应命令的实体行（否则 `invalid_snapshot`）；
- 快照新增命令的回执与请求、运行和实体语义一致（否则 `invalid_snapshot`）。

后两条在写入前重放整个账本，因此“能通过导入”与“能通过 `validate`”不会分离：被拒绝的快照不会改动本机任何字节，也不会把损坏状态再传播给下一个副本。

普通命令只做本机事务，不读写快照，也不改变交换记录。发布窗口只在写入指针前后短暂持有 Git index 锁：

- 锁被别人占用时报 `git_busy`，并保留对方的锁文件；
- 进程被强杀可能遗留 `index.lock`，同时保留 `pending_kind=export` 与已写入的指针；
- 恢复步骤是先确认没有其他 Git/Vibe 写入者，再处理遗留锁，然后用 `state-exchange-finish`（指针与待发布快照一致）或 `state-exchange-abandon`（确认未发布）结束待发布状态。Vibe 不会自动删除任何锁或自动清除待发布状态。

待发布期间仍可接受新的本机命令：`pending_revision` 记录的是发布意图指向的 revision，可以落后于当前 `local_revision`，`state-exchange` 的 `unexported_commands` 会如实显示这些尚未发布的新命令。此时 `validate` 仍然干净，不需要任何修复动作。

`state-export` 只有在快照真正发布并确认后才报告成功；如果交换已经完成、只是随后生成派生视图失败，命令返回 `projection_error`（而不是失败退出），指针与 `exported_local_revision` 已经更新，调用方不应据此重试导出。

### 旧格式项目与显式迁移

`vibe init` 只用于**新建**项目：目标目录已有 `.project-log` 时报告 `skipped` 并保持原样，绝不原地改写现有记录。存量旧格式项目在迁移窗口内继续可用；要切到 format 2，必须显式执行迁移，不能通过删除标记或状态目录绕过。

先只读预演：

```text
--root <project> migrate preview
```

预演不读取文件修改时间，也不猜测业务事实。重复 ID、悬空引用、源摘要变化会阻止切换；未知任务字段、无法转换的旧证据、无法复现完成门禁的任务会进入 `.project-log/legacy/unmapped`，不中止迁移也不删除历史。

确认预演结果后执行：

```text
--root <project> migrate apply --confirm <preview_hash>
--root <project> migrate resume
--root <project> migrate rollback [--destination <dir>]
```

`migrate apply` 先备份旧记录，再生成并校验新存储，最后原子切换标记、旧文件与状态库。迁移日志位于 `.project-log/.migration/journal.json`；中断后用 `migrate resume` 从日志继续。`migrate rollback` 恢复旧格式文件，并先把迁移后的新写入导出到 `.project-log/legacy/new-writes/bundle.json`，不会静默丢弃新记录。

### 版本与 format 1 退役关口

查看框架版本、默认格式与退役阶段状态：

```text
vibe version
vibe --version
```

format 1 的退役分三步，**每一步都需要用户单独确认**，代理不得自行推进：

| 阶段 | 支持范围变化 |
|---|---|
| `stop-writing` | `loopctl`/`vibe` 不再接受 format 1 写入；只读查询与迁移仍可用 |
| `stop-reading` | `status`/`validate`/`restore` 不再解析 format 1；迁移工具仍可离线运行 |
| `stop-support` | 移除迁移工具、旧模板与兼容代码 |

在旧格式项目上，只读命令会输出 `legacy format: migrate with vibe migrate` 指引；旧格式写入在迁移窗口内仍然可用，但每次都会在 stderr 输出弃用提示。完整发布说明见 [RELEASE-NOTES.md](RELEASE-NOTES.md)。
