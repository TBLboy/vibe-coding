# AI 安装指南

本指南用于让 Codex 或其他本机 AI Agent 安装 Vibe Coding Codex Global Core 0.5.0。

## 安装目标

AI 必须完成：

1. 检查最新稳定版 Codex、Python 3 和依赖。
2. 阅读现有 `AGENTS.md` 与 `config.toml`，不得覆盖用户配置。
3. 运行安装器 preflight。
4. 安装全局主 Agent、Skills、runtime 和三个低风险 Hooks。
5. 在临时项目中初始化并验证 `.project-log`。
6. 输出安装路径、备份路径、保留的本地修改和未安装的可选能力。

## 代理要求

框架部分功能（如拉取可选 MCP、GitHub 远端同步等）需要访问外网，安装前确认本机代理客户端已运行：

- 默认监听 `127.0.0.1:10808`。
- 可通过 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量调整；本仓库 `git fetch`/`git push` 失败时也使用该代理重试。
- 代理不可用时，可选 MCP 拉取会失败；核心安装可使用 `--without-mcp` 完成，不要阻塞安装。

## Vibe Python 环境与安装流程

Vibe Coding 的所有控制层（安装器、Hooks、`loopctl`、项目/包校验）默认运行在统一的 `vibe-coding` Python 3.11 虚拟环境中。完整流程如下：

1. 创建虚拟环境（若还没有 Conda，先安装 Miniforge/Miniconda）：

   ```bash
   conda create -y -n vibe-coding python=3.11
   ```

   Windows PowerShell 相同。

2. 激活环境并安装 Vibe 依赖：

   ```bash
   conda activate vibe-coding
   python -m pip install -r runtime/scripts/requirements.txt
   ```

3. 在激活的环境中运行安装器。也可以直接运行包装脚本 `install.sh` / `install.ps1`——包装脚本会先解析或创建 `vibe-coding` 环境，并用该环境的 Python 执行安装器，无需手动激活。

4. 安装器会把该解释器绝对路径写入 `CODEX_HOME/vibe-python`（默认 `~/.codex/vibe-python`），作为框架全局配置；生成的 Hook `command` / `commandWindows` 也绑定该解释器。

5. 后续 Vibe 功能（Hooks、`loopctl`、`validate_project.py`、`validate_package.py` 等）都运行在该环境中，不要用系统 Python 运行它们。

适配不同用户的场景：

- 已存在可用的 `vibe-coding` 环境：安装器直接复用，跳过创建。
- 已有 `CODEX_HOME/vibe-python` 配置：优先复用该解释器，仅在其不可用时才尝试 Conda 修复。
- 没有 Conda/Miniforge/Miniconda：安装器不会静默下载发行版，会明确报错；先安装 Miniforge，或显式设置 `VIBE_PYTHON`。
- 临时覆盖：`export VIBE_PYTHON=/absolute/path/to/python`（优先级最高）；`VIBE_CONDA_ENV` 可覆盖环境名（默认 `vibe-coding`）。

## 推荐给 AI 的指令

```text
请在当前安装包目录执行 Vibe Coding Codex Global Core 安装。

要求：
1. 先阅读 README.md、AI_INSTALL.md 和 scripts/global_installer.py 的参数。
2. 确认 Codex 是当前可升级到的最新稳定版；运行 codex --version、codex doctor 和 codex features list。
3. 确认 Python 3.11+。Vibe 功能统一在 `vibe-coding` 环境中运行；Windows 检查系统解释器时可用 `py -3`，不要使用可能指向 Python 2 的 `python`。
4. 运行安装包装脚本；它会优先复用 `${CODEX_HOME:-$HOME/.codex}/vibe-python`，否则使用 Conda/Miniforge/Miniconda 创建 `vibe-coding` Python 3.11 环境并安装 `runtime/scripts/requirements.txt`；也可用 `VIBE_PYTHON` 临时覆盖。
5. 安装 runtime/scripts/requirements.txt。
6. 默认使用 --access-profile keep-existing，不修改我现有权限配置。
7. 默认不安装可选 MCP；如果用户明确选择，使用 `--mcp codegraph` 或其他 catalog 名称（可重复）。
8. 如果公司网络或 MCP 前置工具不可用，使用 --without-mcp 完成核心安装，不要阻塞核心工作流。
9. 不使用 --skip-preflight。
10. 安装后运行 global_installer.py verify。
11. 创建临时项目，运行已安装的 `vibe.py init`、`vibe.py validate` 和 `vibe.py status`。
12. 不修改或删除任何真实项目的 .project-log。
13. 最后报告版本、CODEX_HOME、Skill 路径、Hook 状态、已选 MCP、备份路径、验证结果和任何限制。
14. 安装前确认本机代理可用（默认 127.0.0.1:10808，可用 HTTP_PROXY/HTTPS_PROXY 调整）；可选 MCP 拉取与远端同步依赖外网。
```

## Windows 执行步骤

```powershell
conda activate vibe-coding
python --version
codex --version
codex doctor
codex features list
python -m pip install -r runtime\scripts\requirements.txt
python scripts\global_installer.py preflight
.\install.ps1
python scripts\global_installer.py verify
```

如用户明确要启用 CodeGraph，可改为 `./install.sh --mcp codegraph`（Windows 使用 `--mcp codegraph`）；默认不启用可选 MCP。

> 以上手动步骤假定已激活 `vibe-coding` 环境；也可以直接运行 `install.sh` / `install.ps1`，包装脚本会自动解析或创建环境并完成依赖安装。

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

## Windows Hook 命令适配（Codex 0.147.0+）

在 Windows 上，Codex 0.147.0 及以上版本不再通过 shell 解析 Hook 命令中的引号。安装器默认生成的 `commandWindows` 形如：

```toml
commandWindows = "\"D:\\conda\\envs\\vibe-coding\\python.exe\" \"...\\session_start.py\""
```

这种带引号形式在 Windows 上会导致 Hook 进程无法启动，终端报 `SessionStart hook (failed) / hook exited with code 1`（Hook 脚本本身直连执行正常）。Linux/macOS 使用 `command` 字段，走 shell 解析，不受影响，无需任何修改。

Windows 适配步骤（仅 Windows 需要）：

1. 打开 `$env:CODEX_HOME\config.toml`（默认 `C:\Users\<用户>\.codex\config.toml`）。
2. 将 `[[hooks.SessionStart]]`、`[[hooks.PostToolUse]]`、`[[hooks.PreCompact]]` 三个 Hook 的 `commandWindows` 改为不带引号的路径形式（本机路径无空格时）：

```toml
commandWindows = "D:\\conda\\envs\\vibe-coding\\python.exe C:\\Users\\<用户>\\.codex\\vibe-workflow\\hooks\\session_start.py"
```

3. 保持 `command` 字段不变（带引号形式，供 Linux/macOS 使用）。
4. 删除 `[hooks.state]` 下对应的 `trusted_hash` 条目，或在下一次启动时重新信任 Hook。
5. 验证：运行 `codex exec "say OK"`，终端输出 `hook: SessionStart Completed` 即适配成功。

> 注意：`commandWindows` 路径若包含空格，则需要保留引号或用短路径/环境变量替代；当前 Vibe 默认路径不含空格。

## Linux/macOS 执行步骤

```bash
conda activate vibe-coding
python --version
codex --version
codex doctor
codex features list
python -m pip install -r runtime/scripts/requirements.txt
python scripts/global_installer.py preflight
./install.sh
python scripts/global_installer.py verify
```

## 临时项目验收

Windows：

```powershell
$TestProject = Join-Path $env:TEMP "vibe-codex-smoke"
New-Item -ItemType Directory -Force -Path $TestProject | Out-Null
python "$env:CODEX_HOME\vibe-workflow\scripts\vibe.py" init --root $TestProject
python "$env:CODEX_HOME\vibe-workflow\scripts\vibe.py" --root $TestProject validate
python "$env:CODEX_HOME\vibe-workflow\scripts\vibe.py" --root $TestProject status
```

若未设置 `CODEX_HOME`，默认使用 `$HOME/.codex`。

## 首次使用

1. 打开真实项目。
2. 输入：`vibe 开始：<需求>`。
3. 完成功能业务逻辑、技术业务逻辑和双向对齐。
4. 建立 Project Goal。
5. 使用 Codex 原生 `/goal` 绑定 `loopctl goal-bind` 生成的 objective。
6. 原生 Goal 完成后执行 Project Goal 验收。

首次运行 Hooks 时 Codex 可能要求确认 Hook trust。只在确认安装目录和脚本内容正确后信任。

## 禁止事项

- 不以 `--skip-preflight` 完成真实安装。
- 不默认使用 full access。
- 不用 Stop Hook 或外层脚本替代原生 `/goal`。
- 不在多个 Skill 根目录重复复制同名 Skill。
- 不覆盖安装器报告的本地修改或升级冲突。
