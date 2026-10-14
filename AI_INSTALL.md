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
   `opencode.json`），并按其选择把可选集成目录
   `runtime/opencode/optional-integrations.json` 里的插件（默认含固定版本的会话 Goal 控制器
   `@prevalentware/opencode-goal-plugin@0.1.60` 与 `opencode-agent-memory`）与 MCP 工具带
   （`context7`、`gh_grep`、`document-loader`、`github`、`playwright`、
   `sequential-thinking`、`web-search`、`wikipedia`）合并进 `plugin`/`plugins` 与 `mcp` 段。
   可用 `--list-integrations` 查看清单与当前选择，用 `--with-plugin/--without-plugin/
   --with-mcp/--without-mcp` 调整。默认安装的会话 Goal 控制器带内建上限，装完必须按
   下文《会话 Goal 插件的内建上限》处理，否则长任务会被它中途停下。
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

## 会话 Goal 插件的内建上限（安装后必须处理）

可选集成 `goal`（`@prevalentware/opencode-goal-plugin@0.1.60`）带内建上限。默认安装写入的是
受管的**字符串**条目，插件因此使用自己的默认值，长任务会在跑到一半时被它停下：

| 选项 | 插件默认值 | 到顶后的表现 |
|---|---|---|
| `max_auto_turns` | 25 | 累计自动续跑回合到顶，goal 变 `usageLimited`，停止续跑 |
| `max_no_progress_turns` | 2 | 连续无进展的续跑回合到顶，暂停 |
| `max_prompt_failures` | 3 | 续跑提示连续失败到顶，暂停 |
| `default_token_budget` | 未设置 | 默认无 token 预算；只有 goal 显式带 `token_budget` 才 `budgetLimited` |
| `max_goal_duration_seconds` | 未设置 | 默认无时长上限 |

**`0` 不等于"无上限"。** 插件按 `positiveIntegerOrNull(v) => v > 0 ? v : null` 解析，写 `0`
会被判为无效并**回退默认值**（例如 `max_auto_turns` 回到 25）。解除上限要写一个极大的合法整数。

处理步骤（安装后执行一次，已在 `opencode 2.0.27` 上验证）：

1. 把 goal 条目从字符串改成带选项的元组（配置 schema 明确支持 `["pkg", {options}]`；V2 通过
   `setup(context).options` 把选项交给插件）：

   ```json
   "plugin": [
     [
       "@prevalentware/opencode-goal-plugin@0.1.60",
       {
         "max_auto_turns": 1000000000,
         "max_no_progress_turns": 1000000000,
         "max_prompt_failures": 1000000000
       }
     ],
     "opencode-agent-memory"
   ]
   ```

2. **紧接着**把该集成从安装器选择里去选择，交还给用户自有：

   ```bash
   ./runtime/opencode/install.sh update --without-plugin goal
   ```

   这一步不能省。安装器只按字符串识别受管插件（`plugin_package_name()` 对非字符串返回
   `None`）：留着 goal 被选中时，`verify` 会因为"已选中的 goal 未被识别为已注册"报错；而不
   报错的那条路径会再追加一条固定字符串条目，导致**同一插件被注册两次**。去选择后
   `selected_integrations.plugins` 里不再有 `goal`，后续 `update` 不会改动这条元组。

3. 使配置生效：

   ```bash
   opencode reload
   ```

   配置热加载，不必重启客户端；重载后 `/goal`、`/pause_goal`、`/resume_goal` 仍在，插件状态为
   `active`。

要确认选项真的送达了插件（排障时先做这一步）：临时加入 `"register_command": false` →
`opencode reload` → `opencode api GET /api/command` 里 `goal` 消失；删掉该键再重载，命令恢复。

其他要点：

- **注入式提醒无法用配置关闭。** 插件在 `context` 钩子里每轮注入 "goal mode policy"（含"先调用
  `get_goal`"），没有对应选项；它只读、无害。要彻底消除只能 `--without-plugin goal` 卸载该
  插件（Project Goal 存在 `.project-log`，不受影响）。
- **插件不会自己创建 goal。** 它没有自动创建路径，创建只来自显式工具调用；没有 goal 就不会自动
  续跑，上表的上限也无从触发。
- 只想去掉自动续跑、保留 `/goal` 手动控制：在选项里写 `"auto_continue": false`。两个
  `reserveContinuation` 调用点都在 `if (!autoContinue) return;` 之后，上限因此全部不可达。
- 要恢复插件默认上限：删掉元组里的选项（退回字符串条目）并
  `./runtime/opencode/install.sh update --with-plugin goal`。

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
2. 不得覆盖用户已有的 AGENTS.md 内容、opencode.json 插件/MCP/权限设置。受管条目只在用户
   没有同名条目时写入；用户改过或删过的受管条目不会被覆盖，也不会在下次 update 复活。
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
| `--with-plugin NAME` / `--without-plugin NAME` | 启用/停用可选插件（可重复；名称见 `optional-integrations.json`） |
| `--with-mcp NAME` / `--without-mcp NAME` | 启用/停用可选 MCP 服务（可重复） |
| `--list-integrations` | 打印可选集成目录、默认值与当前选择，不写任何文件 |
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
- 不得给 `goal` 集成写入选项后仍让它留在安装器选择里——必须同时
  `./runtime/opencode/install.sh update --without-plugin goal`，否则会重复注册或让 `verify`
  失败。
- 不得在源码树内创建 `.project-log/` 或临时测试产物。
- Windows（PowerShell 5.1/7）实机矩阵尚未验证，本版支持范围为 Linux/WSL。
