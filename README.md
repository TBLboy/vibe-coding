# Vibe Coding — OpenCode 版

面向 **OpenCode** 客户端的用户级全局 Vibe Coding 工作流。本分支（`opencode`）从 `main`
独立派生，不继承 `codex` 分支的提交历史；它与 codex 版**功能对齐、各自独立演进**。

> **安装入口是 `./runtime/opencode/install.sh`。**
> 仓库根目录的 `install.sh` / `update.sh` / `uninstall.sh`（及 `.ps1`）是 **codex 面**的
> 遗留入口，由 `scripts/global_installer.py` 驱动、安装到 `~/.codex`。它们为保留的
> codex 交付面服务，**不是** OpenCode 版的入口。OpenCode 客户端的完整表面文档见
> [runtime/opencode/README.md](runtime/opencode/README.md)。

## 使用指南

以真实开发任务讲解完整使用流程（初始化工程 → 业务逻辑澄清 → 技术选型 → 代码落地 →
归档留痕），见 [docs/USAGE.md](docs/USAGE.md)。

format 2 是唯一受支持的 Project Log 格式，format 1 的退役与历史存档见
[docs/RELEASE-NOTES.md](docs/RELEASE-NOTES.md)。

## 核心能力

- 在用户级 `~/.config/opencode/AGENTS.md` 注入可增量更新的 Vibe 主 Agent 规则。
- 安装全部内置 Skills（36 个），包括双域业务澄清、Loop Control 与动态 Subagent 编排。
- 提供宿主无关的 `.project-log/`：format 2/3 的业务事实、需求基线、技术研究、架构、任务、
  验证、对齐与长期恢复状态。
- 一个 primary agent（`vibe-main`）+ 八个受限 subagent（`business-analyst`、
  `codebase-onboarder`、`solution-researcher`、`implementation-builder`、
  `verification-reviewer`、`alignment-reviewer`、`paper-reader`、`workflow-distiller`），
  通过 OpenCode 原生 `task` 工具编排，权限按角色边界收窄。
- 会话 Goal 控制面由固定版本 `@prevalentware/opencode-goal-plugin@0.1.51` 承担
  （`/goal`、`/pause_goal`、`/resume_goal`）；**Project Goal 仍是唯一完成契约**，
  插件状态永不作为完成依据。
- 七个生命周期命令：`/vibe-start`、`/vibe-resume`、`/vibe-plan`、`/vibe-implement`、
  `/vibe-verify`、`/vibe-status`、`/vibe-retro`。
- 逐文件三方升级，保护用户本地修改；升级冲突在写入前停止。
- `vibe` CLI 与同一套 `.project-log` 事实源，不创建第二套业务记录。

## 环境要求

- OpenCode CLI（本版在 `1.18.31` 上验证）。
- Python 3.11 或更高版本。
- 代理：部分功能需要访问外网，本机默认代理监听 `127.0.0.1:10808`；
  可通过 `HTTP_PROXY`/`HTTPS_PROXY` 调整。

### 全局 Vibe Python

安装器会优先复用 `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python`；如果不存在，
会寻找 Conda/Miniforge/Miniconda，自动创建名为 `vibe-coding` 的 Python 3.11 环境并安装
[`runtime/scripts/requirements.txt`](runtime/scripts/requirements.txt)，然后把该解释器路径
写入全局配置。没有 Conda 时安装器会明确报错，不会静默下载大型发行版，也不会静默切换到
系统 Python。

## 安装

建议由 AI 按 [AI_INSTALL.md](AI_INSTALL.md) 执行，或直接运行：

```bash
chmod +x runtime/opencode/install.sh
./runtime/opencode/install.sh install     # 无参数时默认 install
./runtime/opencode/install.sh verify
./runtime/opencode/install.sh update
./runtime/opencode/install.sh uninstall
```

常用选项：

| 选项 | 作用 |
|---|---|
| `--opencode-home <dir>` | 目标配置目录，默认 `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}` |
| `--skip-plugin-install` | 不运行包管理器安装 `@opencode-ai/plugin` |
| `--skip-preflight` | 跳过工具探测，仅用于隔离的包测试 |

默认行为：

- `AGENTS.md` 以标记块（`<!-- VIBE-OPENCODE-GLOBAL:BEGIN -->` … `END`）合并，用户已有规则被保留。
- `opencode.json` 采用合并而非覆盖：设置 `default_agent`、注册插件与权限规则，同时保留用户
  自己的 `plugin`、`mcp`、`model`、`permission` 等键。
- 备份到 `<home>/backups/<action>-<stamp>/`。
- 安装、升级、卸载对其触及的文件是事务性的；失败会回滚。

## 升级

老版本升级见 [AI_UPGRADE.md](AI_UPGRADE.md)。

```bash
./runtime/opencode/install.sh update
```

逐文件三方规则：

- 用户未修改、新包有变化：升级。
- 用户已修改、新包未变化：保留用户修改并报告。
- 用户和新包都修改同一文件：写入前停止并报告冲突。
- 新包删除、用户修改过：保留并报告。

## 验证

```bash
# 安装面自检
./runtime/opencode/install.sh verify

# 包结构与 Skills 契约
"$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")" runtime/scripts/validate_package.py --root .

# 回归套件
"$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")" -m unittest discover -s tests

# 真实 OpenCode 端到端验收（S1–S6）
# 探针位于工作目录的 .project-log/docs/ 下（不在本仓库内）
"$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")" \
  <工作目录>/.project-log/docs/opencode-acceptance-probe.py \
  --phases s1,s2,s3,s4,s5,s6 --model opencode-go/glm-5.3-flash --seconds 150
```

项目初始化与校验：

```bash
"$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")" \
  "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-workflow/scripts/vibe.py" init \
  --root /path/to/project
```

## Vibe CLI

```text
vibe init
vibe status
vibe validate
vibe route --signal ...
vibe task begin|update|wait|resume|handoff|finish|cancel
vibe record create|update|link
vibe evidence record|invalidate|refresh
vibe review record
vibe gate --task TASK-ID
vibe goal update|complete --id GOAL-ID
```

Project Log format 2 是唯一受支持的格式；日常操作与文档示例统一走 `vibe`。
会话 Goal 显示完成后，仍需通过 `vibe goal complete` 的证据门禁才能完成 Project Goal。

## 卸载

```bash
./runtime/opencode/install.sh uninstall
```

卸载仅移除包拥有且未被用户修改的文件、受管 `AGENTS.md` 块、插件注册与受管权限规则。
项目中的 `.project-log/` 永不删除。

## 平台范围

- **支持**：Linux / WSL。
- **延期**：Windows（PowerShell 5.1/7 实机矩阵未验证，见
  工作目录 `.project-log/docs/task-043-cross-platform-acceptance.md`）。

## 客户端差异与保留的 codex 面

- OpenCode 与 codex 的行为差异、能力对齐矩阵见
  [runtime/opencode/README.md](runtime/opencode/README.md) 与
  工作目录 `.project-log/docs/opencode-parity-matrix.md`。
- 仓库仍保留 codex 交付面（`runtime/agents/`、`runtime/hooks/`、`prompts/vibe-global-agent.md`、
  `scripts/global_installer.py`、根目录的 `install.*`/`update.*`/`uninstall.*`、
  `runtime/mcp/optional-mcps.json`）。`validate_package.py` 的 `REQUIRED_*` 契约要求它们存在，
  它们服务 codex 客户端，与 OpenCode 面**互不污染**。
- 两个版本共享的业务规则变更必须**显式同步**，不自动合并。
