# AI 安装指南（OpenCode）

本指南用于让 OpenCode 或其他本机 AI Agent 安装 **Vibe Coding — OpenCode Global Core 0.6.0**。

> 仓库根目录的 `install.sh` / `install.ps1` 及 `scripts/global_installer.py` 是 codex 面的遗留
> 入口（安装到 `~/.codex`），**不要**用它们安装 OpenCode 版。OpenCode 版的入口是
> `runtime/opencode/install.sh` 与 `scripts/opencode_installer.py`。

## 安装目标

AI 必须完成：

1. 检查 OpenCode CLI、Python 3.11+ 和依赖。
2. 阅读现有的 `AGENTS.md` 与 `opencode.json`，不得覆盖用户已有的规则、插件、MCP 或权限设置。
3. 运行安装器 preflight。
4. 安装全局主 Agent、八个受限 subagent、七个生命周期命令、全部内置 Skills、runtime、
   `vibe-workflow` 插件，并注册固定版本的会话 Goal 控制器
   `@prevalentware/opencode-goal-plugin@0.1.51`。
5. 在临时项目中初始化并验证 `.project-log`。
6. 输出安装路径、备份路径、保留的本地修改和未安装的可选能力。

## 代理要求

框架部分功能（如拉取可选 MCP、GitHub 远端同步等）需要访问外网，安装前确认本机代理客户端已运行：

- 默认监听 `127.0.0.1:10808`；可通过 `HTTP_PROXY`/`HTTPS_PROXY` 调整。

## Vibe Python 环境与安装流程

安装器按以下顺序解析解释器：

1. 优先复用 `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python` 指向的路径；
2. 不存在时，寻找 Conda/Miniforge/Miniconda，创建或修复名为 `vibe-coding` 的 Python 3.11 环境，
   安装 `runtime/scripts/requirements.txt`，并把绝对路径写入全局 `vibe-python`；
3. 没有 Conda 时**明确报错并停止**，不静默下载大型发行版，也不静默切换到系统 Python。

该解释器必须是 Python 3.11+，并已安装 `PyYAML` 与 `jsonschema`。

也可以手动指定（写入后跨项目、跨会话生效）：

```bash
mkdir -p "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
printf '%s\n' '/absolute/path/to/miniforge3/envs/vibe-coding/bin/python' \
  > "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python"
```

环境变量 `VIBE_PYTHON` 优先级高于该文件。

## 推荐给 AI 的指令

```text
请阅读本仓库的 AI_INSTALL.md，按其中的步骤把 Vibe Coding OpenCode Global Core
安装到 ${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}。

要求：
1. 安装前先运行 preflight，并阅读现有的 AGENTS.md 与 opencode.json。
2. 不得覆盖用户已有的 AGENTS.md 内容、opencode.json 插件/MCP/权限设置。
3. 安装后运行 verify，并在临时项目中完成一次初始化与校验。
4. 输出：安装路径、备份路径、保留的本地修改、未安装的可选能力。
5. 遇到冲突（同名文件内容不一致）必须停止并报告，不要强制覆盖。
```

## Linux/macOS 执行步骤

```bash
chmod +x runtime/opencode/install.sh
./runtime/opencode/install.sh preflight
./runtime/opencode/install.sh install
./runtime/opencode/install.sh verify
```

常用选项：

| 选项 | 作用 |
|---|---|
| `--opencode-home <dir>` | 目标配置目录，默认 `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}` |
| `--skip-plugin-install` | 不运行包管理器安装 `@opencode-ai/plugin` |
| `--skip-preflight` | 跳过工具探测，仅用于隔离的包测试 |

## 临时项目验收

```bash
PY="$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")"
VIBE="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-workflow/scripts/vibe.py"
TMP="$(mktemp -d)"
"$PY" "$VIBE" init --root "$TMP"
"$PY" "$VIBE" --root "$TMP" validate
"$PY" "$VIBE" --root "$TMP" status
rm -rf "$TMP"
```

上面第一条命令展开后即：

```bash
"$PY" "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-workflow/scripts/vibe.py" init --root "$TMP"
```

期望：`init` 在临时目录生成 format 2 的 `.project-log/`；`validate` 返回 `{"errors": []}`；
`status` 输出 `project_id` 与 `revision`。临时目录用后删除，不要留在源码树内。

## 首次使用

1. 在目标项目根目录让 Agent 执行：

   ```bash
   "$PY" "$VIBE" init --root <项目根>
   ```

2. 用自然语言或斜杠命令开始：`/vibe-start`、`/vibe-plan`、`/vibe-implement`、
   `/vibe-verify`、`/vibe-status`、`/vibe-retro`、`/vibe-resume`。
3. 会话 Goal 由固定版本插件承担（`/goal`、`/pause_goal`、`/resume_goal`）；
   **Project Goal 才是唯一完成契约**，插件状态不能作为完成依据。

## 禁止事项

- 不得用仓库根的 `install.sh` / `install.ps1` 安装 OpenCode 版（那是 codex 面）。
- 不得覆盖或删除用户已有的 `AGENTS.md` 内容、`opencode.json` 设置或 `.project-log/`。
- 不得静默切换解释器版本，也不得在缺少 Conda 时静默使用系统 Python。
- 不得在源码树内创建 `.project-log/` 或临时测试产物。
- Windows（PowerShell 5.1/7）实机矩阵尚未验证，本版支持范围为 Linux/WSL。
