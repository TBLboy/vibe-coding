# AI 安装指南（OpenCode）

本指南用于让 OpenCode 或其他本机 AI Agent 安装 **Vibe Coding — OpenCode Global Core 0.6.0**。

> OpenCode 版的入口是 `runtime/opencode/install.sh` 与 `scripts/opencode_installer.py`。
> 仓库**不含** codex 交付面（根目录安装脚本、`scripts/global_installer.py` 等已移除），
> codex 版在 `codex` 分支独立维护。

## 安装目标

AI 必须完成：

1. 检查 OpenCode CLI（必须是 **V2**，即 `opencode --version` 为 2.x；V1 不再支持）、Python 3.11+ 和依赖。
   只装了桌面版时 CLI 不在 PATH，位于 `/opt/OpenCode/resources/opencode-cli`，先软链：
   `ln -sf /opt/OpenCode/resources/opencode-cli ~/.local/bin/opencode`。
   shell 里设置了其他 Python 的 `PYTHONPATH`（例如 ROS）时，先 `unset PYTHONPATH` 再执行安装与验收命令。
2. 阅读现有的 `AGENTS.md` 与 `opencode.json`，不得覆盖用户已有的规则、插件、MCP 或权限设置。
3. 运行安装器 preflight。
4. 安装全局主 Agent、八个受限 subagent、七个生命周期命令、全部内置 Skills、runtime、
   `vibe-workflow` V2 目录插件（`plugins/vibe-workflow/index.ts`，由 OpenCode 自动发现，不写入
   `opencode.json`），并注册固定版本的会话 Goal 控制器
   `@prevalentware/opencode-goal-plugin@0.1.60`。
5. 在临时项目中初始化并验证 `.project-log`。
6. 输出安装路径、备份路径、保留的本地修改和未安装的可选能力。

## 代理要求

框架部分功能（如拉取可选 MCP、GitHub 远端同步等）需要访问外网，安装前确认本机代理客户端已运行：

- 默认监听 `127.0.0.1:10808`；可通过 `HTTP_PROXY`/`HTTPS_PROXY` 调整。

## 全局默认模型（必配，否则后台委派静默失败）

安装器只写入 `default_agent`，**不写 `model`**。因此安装后必须在全局 `opencode.json` 顶层
显式声明一个本机网络下可用的模型：

```json
{ "model": "opencode-go/deepseek-v4.1-flash" }
```

不配的后果：后台委派通道（`delegate` / background-agents 插件）创建子会话时不声明 agent，
因此**不继承父会话的模型**，而是回落到这个全局默认模型。若它缺失，或指向当前地区被上游拒绝的
模型，每次委派都会在约 1 秒内以
`AI_APICallError: Country, region, or territory not supported` 失败，而插件仍会写入
`status: complete` 与空结果——**表现为静默失败，极易被误判为成功**。
原生 `task` 工具继承父会话模型，不受此影响，所以这种故障只在后台委派里出现。

修改顶层 `model` 后需重启 OpenCode 才生效（配置不热加载）。

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
| `--skip-plugin-install` | 兼容旧调用而保留，无任何作用：OpenCode V2 自带插件 API，不再安装 npm 依赖 |
| `--skip-preflight` | 跳过工具探测，仅用于隔离的包测试 |

## 临时项目验收

```bash
PY="$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")"
VIBE="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-workflow/scripts/vibe.py"
TMP="$(mktemp -d)"
"$PY" "$VIBE" --root "$TMP" init
"$PY" "$VIBE" --root "$TMP" validate
"$PY" "$VIBE" --root "$TMP" status
rm -rf "$TMP"
```

上面第一条命令展开后即：

```bash
"$PY" "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-workflow/scripts/vibe.py" --root "$TMP" init
```

`--root` 是全局参数，必须写在子命令（`init`、`validate`、`status` 等）**之前**；写在后面会报
`unrecognized arguments: --root`。

期望：`init` 在临时目录生成 format 2 的 `.project-log/`；`validate` 返回 `{"errors": []}`；
`status` 输出 `project_id` 与 `revision`。临时目录用后删除，不要留在源码树内。

## 首次使用

1. 在目标项目根目录让 Agent 执行：

   ```bash
   "$PY" "$VIBE" --root <项目根> init
   ```

2. 用自然语言或斜杠命令开始：`/vibe-start`、`/vibe-plan`、`/vibe-implement`、
   `/vibe-verify`、`/vibe-status`、`/vibe-retro`、`/vibe-resume`。
3. 会话 Goal 由固定版本插件承担（`/goal`、`/pause_goal`、`/resume_goal`）；
   **Project Goal 才是唯一完成契约**，插件状态不能作为完成依据。

## 禁止事项

- 不得使用仓库根目录的安装脚本安装 OpenCode 版——本分支已不含它们，入口只有
  `runtime/opencode/install.sh`。
- 不得覆盖或删除用户已有的 `AGENTS.md` 内容、`opencode.json` 设置或 `.project-log/`。
- 不得静默切换解释器版本，也不得在缺少 Conda 时静默使用系统 Python。
- 不得在源码树内创建 `.project-log/` 或临时测试产物。
- Windows（PowerShell 5.1/7）实机矩阵尚未验证，本版支持范围为 Linux/WSL。
