# Vibe Coding - Codex Global Core 0.4.1

面向 Codex CLI、VS Code 插件、桌面端与 ACP 外部协议连接端等 Codex 客户端的用户级全局 Vibe Coding 工作流。

## 使用指南

以真实开发任务讲解完整使用流程（初始化工程 → 业务逻辑澄清 → 技术选型 → 代码落地 → 归档留痕），见 [docs/USAGE.md](docs/USAGE.md)。

## 核心能力

- 在用户级 `AGENTS.md` 中注入可增量更新的 Vibe 主 Agent 规则。
- 安装全部内置 Skills，包括双域业务澄清、Loop Control 和动态 Subagent 编排。
- 提供宿主无关的 `.project-log/`：业务事实、需求基线、技术研究、架构、任务、验证、对齐和长期恢复状态。
- 在 `business-clarification` 内分别维护功能业务逻辑、技术业务逻辑和双向对齐，不增加新的生命周期阶段。
- 使用 Codex 原生 `/goal` 作为唯一线程运行和 continuation 控制器。
- 使用 `loopctl` 管理 Project Goal、证据有效性、失败归因、Retry Contract、有限循环和 Handoff。
- 安装三个低风险 command Hooks：`SessionStart`、`PostToolUse`、`PreCompact`。
- 逐文件三方升级，保护用户本地修改；升级冲突在写入前停止。
- 通过声明式 catalog 管理可选 MCP；新安装默认只安装核心，不强制安装任何 MCP。

## 工作流

```text
业务逻辑澄清
  ├── 功能业务逻辑
  ├── 技术业务逻辑
  └── 双向对齐
→ 技术选型
→ 任务拆解
→ 需求描述
→ 验证落地
```

外层 Loop：

```text
恢复 → 有限工作单元 → 执行 → 证据 → 失败归因
→ 继续 / 差异化返工 / 回退 / 完成 / Handoff
```

## 环境要求

- 安装时最新稳定版 Codex。
- Python 3.11 或更高版本。
- Windows 使用 `py -3`，不要假设 `python` 指向 Python 3。
- 代理：部分功能（如拉取可选 MCP、GitHub 远端同步等）需要访问外网，本机需运行代理客户端，默认监听 `127.0.0.1:10808`；可通过 `HTTP_PROXY`/`HTTPS_PROXY` 环境变量调整。
- Python 依赖：

```powershell
py -3 -m pip install -r runtime\scripts\requirements.txt
```

### 全局 Vibe Python

安装器会优先复用 `$CODEX_HOME/vibe-python`；如果不存在，会寻找 Conda/Miniforge/Miniconda，并自动创建名为 `vibe-coding` 的 Python 3.11 环境，安装 `runtime/scripts/requirements.txt`，然后将该环境写入全局配置。

Linux/macOS 推荐直接运行（默认不安装可选 MCP）：

```bash
./install.sh
```

如果机器没有 Conda/Miniforge/Miniconda，安装器不会静默下载大型发行版，而是给出明确错误；可以先安装 Miniforge，或显式设置 `VIBE_PYTHON`。也可以手动指定环境：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}"
printf '%s\n' '/absolute/path/to/miniforge3/envs/vibe-coding/bin/python' \
  > "${CODEX_HOME:-$HOME/.codex}/vibe-python"
```

也可以临时用环境变量覆盖：

```bash
export VIBE_PYTHON='/absolute/path/to/miniforge3/envs/vibe-coding/bin/python'
```

配置文件优先用于跨项目和新 Codex 会话；环境变量优先级更高。该解释器必须是 Python 3.11+，并安装 `PyYAML` 和 `jsonschema`。

Linux/macOS：

```bash
python3 -m pip install -r runtime/scripts/requirements.txt
```

## 安装

建议由 AI 按 [AI_INSTALL.md](AI_INSTALL.md) 执行。

Windows：

```powershell
.\install.ps1
```

Windows 部署完成后，如启动 Codex 报 Hook 失败，按 [AI_INSTALL.md](AI_INSTALL.md) 中“Windows Hook 命令适配（Codex 0.147.0+）”一节处理；Linux/macOS 无需适配。

Linux/macOS：

```bash
chmod +x install.sh update.sh uninstall.sh
./install.sh
```

默认行为：

- 保留现有 Codex 权限配置。
- 启用三个低风险 Hooks。
- 自动备份到 `<CODEX_HOME>/backups/`。
- 新安装默认不启用可选 MCP；用 `--mcp NAME` 显式选择。
- `--without-mcp` 保留为兼容参数，显式跳过所有可选 MCP，适合公司受限网络。

可选访问配置：

```powershell
.\install.ps1 --access-profile workspace
.\install.ps1 --access-profile full
```

只有显式指定时才修改访问配置；若用户已有权限设置，安装器拒绝覆盖。

## cc-switch 通用配置

使用 cc-switch 切换 Codex 供应商时，需要把本框架生成的 TOML 段覆盖到 cc-switch 的“通用配置”中：

1. 按当前宿主机生成配置（生成结果含本机绝对路径，**不要跨机器复制**）：

   ```bash
   python scripts/generate_cc_switch_config.py --output cc-switch-common-config-codex.txt
   ```

2. 打开 cc-switch 的通用配置，用生成文件的内容（`# VIBE-CODEX-GLOBAL:CONFIG:BEGIN` 到 `# VIBE-CODEX-GLOBAL:CONFIG:END` 之间的 TOML 段）覆盖原对应段。
3. 切换供应商后，重新启动 Codex 会话，使 Hooks、marketplace 与插件配置生效。

生成内容包含：

- `model_reasoning_effort` 与 `disable_response_storage`。
- 三个 Hooks：`SessionStart`、`PostToolUse`、`PreCompact`（路径按宿主机解析）。
- 本地 `vibe-global-toolbox` marketplace 与 `vibe-toolbelt` 插件启用配置。

仓库内 `cc-switch-common-config-codex.txt` 仅为当前宿主机的生成结果快照，换机器后请重新生成。

## 升级

老版本升级见 [AI_UPGRADE.md](AI_UPGRADE.md)。

Windows：

```powershell
.\update.ps1
```

Linux/macOS：

```bash
./update.sh
```

0.3.0 旧安装状态会在整树 hash 未变化时自动迁移为逐文件状态。规则：

- 用户未修改、新包有变化：升级。
- 用户已修改、新包未变化：保留用户修改并报告。
- 用户和新包都修改同一文件：写入前停止并报告冲突。
- 新包删除、用户修改过：保留并报告。

## 验证

```powershell
py -3 scripts\global_installer.py verify
py -3 runtime\scripts\validate_package.py --root .
py -3 -m unittest discover -s tests -v
```

项目初始化与验证：

```powershell
py -3 "$env:CODEX_HOME\vibe-workflow\scripts\init_project.py" --target C:\path\to\project
py -3 "$env:CODEX_HOME\vibe-workflow\scripts\validate_project.py" --root C:\path\to\project
```

## Loop CLI

```text
loopctl init
loopctl restore
loopctl status
loopctl start-run --task-id TASK-NEW
loopctl goal-bind
loopctl goal-sync
loopctl record-event
loopctl record-evidence
loopctl invalidate-evidence
loopctl evaluate goal
loopctl decide
loopctl handoff
loopctl validate
```

原生 `/goal` 显示完成后，仍需通过 `loopctl evaluate goal` 才能完成 Project Goal。

## 卸载

```powershell
.\uninstall.ps1
```

卸载仅移除包拥有且未被用户修改的文件、受管 `AGENTS.md` 块和 Hook 配置块。项目中的 `.project-log/` 永不删除。

## 可选 MCP

可选 MCP 声明在 `runtime/mcp/optional-mcps.json`，安装器不会默认强制安装。当前 catalog 包含：

- `codegraph`：为工程建立代码图谱、符号关系和调用/影响分析；优先使用 PATH 中的 `codegraph`，否则回退到 `npx`。
- `vibe-toolbelt`：Vibe Coding 的文档、浏览器、文档处理和 Web 研究工具集。

按需选择一个或多个 MCP（`--mcp` 可重复）：

```bash
./install.sh --mcp codegraph
./update.sh --mcp codegraph --mcp vibe-toolbelt
```

Windows：

```powershell
.\install.ps1 --mcp codegraph
```

检查可选 MCP：

```bash
codex mcp list
codex mcp get codegraph
```

`--without-mcp` 只表示本次安装/升级不处理可选 MCP，不会阻塞核心安装。包不存储 API key 或 token。
