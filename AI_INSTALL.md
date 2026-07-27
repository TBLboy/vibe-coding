# AI 安装指南

本指南用于让 Codex 或其他本机 AI Agent 安装 Vibe Coding Codex Global Core 0.4.0。

## 安装目标

AI 必须完成：

1. 检查最新稳定版 Codex、Python 3 和依赖。
2. 阅读现有 `AGENTS.md` 与 `config.toml`，不得覆盖用户配置。
3. 运行安装器 preflight。
4. 安装全局主 Agent、Skills、runtime 和三个低风险 Hooks。
5. 在临时项目中初始化并验证 `.project-log`。
6. 输出安装路径、备份路径、保留的本地修改和未安装的可选能力。

## 推荐给 AI 的指令

```text
请在当前安装包目录执行 Vibe Coding Codex Global Core 安装。

要求：
1. 先阅读 README.md、AI_INSTALL.md 和 scripts/global_installer.py 的参数。
2. 确认 Codex 是当前可升级到的最新稳定版；运行 codex --version、codex doctor 和 codex features list。
3. 确认 Python 3.11+。Windows 必须使用 py -3，不要使用可能指向 Python 2 的 python。
4. 运行安装包装脚本；它会优先复用 `${CODEX_HOME:-$HOME/.codex}/vibe-python`，否则使用 Conda/Miniforge/Miniconda 创建 `vibe-coding` Python 3.11 环境并安装 `runtime/scripts/requirements.txt`；也可用 `VIBE_PYTHON` 临时覆盖。
5. 安装 runtime/scripts/requirements.txt。
6. 默认使用 --access-profile keep-existing，不修改我现有权限配置。
7. 如果公司网络或 MCP 前置工具不可用，使用 --without-mcp 完成核心安装，不要阻塞核心工作流。
8. 不使用 --skip-preflight。
9. 安装后运行 global_installer.py verify。
10. 创建临时项目，运行已安装的 init_project.py、validate_project.py、loopctl.py restore 和 loopctl.py validate。
11. 不修改或删除任何真实项目的 .project-log。
12. 最后报告版本、CODEX_HOME、Skill 路径、Hook 状态、备份路径、验证结果和任何限制。
```

## Windows 执行步骤

```powershell
py -3 --version
codex --version
codex doctor
codex features list
py -3 -m pip install -r runtime\scripts\requirements.txt
py -3 scripts\global_installer.py preflight
.\install.ps1 --without-mcp
py -3 scripts\global_installer.py verify
```

如确认本机具备 MCP 前置条件，可省略 `--without-mcp`。

## Linux/macOS 执行步骤

```bash
python3 --version
codex --version
codex doctor
codex features list
python3 -m pip install -r runtime/scripts/requirements.txt
python3 scripts/global_installer.py preflight
./install.sh --without-mcp
python3 scripts/global_installer.py verify
```

## 临时项目验收

Windows：

```powershell
$TestProject = Join-Path $env:TEMP "vibe-codex-smoke"
New-Item -ItemType Directory -Force -Path $TestProject | Out-Null
py -3 "$env:CODEX_HOME\vibe-workflow\scripts\init_project.py" --target $TestProject
py -3 "$env:CODEX_HOME\vibe-workflow\scripts\validate_project.py" --root $TestProject
py -3 "$env:CODEX_HOME\vibe-workflow\scripts\loopctl.py" --root $TestProject --json restore
py -3 "$env:CODEX_HOME\vibe-workflow\scripts\loopctl.py" --root $TestProject --json validate
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
