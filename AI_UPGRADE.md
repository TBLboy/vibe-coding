# AI 升级指南（OpenCode）

适用于已经安装旧版 **Vibe Coding — OpenCode Global Core**，需要升级到 **0.6.0** 的电脑。

> OpenCode 版的升级入口是 `runtime/opencode/install.sh update`。仓库**不含** codex 交付面
> （根目录 `update.sh` / `update.ps1`、`scripts/global_installer.py` 等已移除）。

本版本把 Project Log format 2 确立为唯一受支持的格式，并完成 format 1 退役。升级前先阅读
[docs/RELEASE-NOTES.md](docs/RELEASE-NOTES.md)。

## 升级保证

- 安装前自动创建时间戳备份到 `<home>/backups/<action>-<stamp>/`。
- 支持读取旧版安装状态文件。
- 旧 runtime 与 Skill 整树未被用户修改时，可自动迁移到逐文件升级状态。
- 升级对其触及的文件是事务性的：任一步失败会恢复先前的字节，并移除本次新建的目录。

## 逐文件三方规则

- 用户未修改、新包有变化：升级。
- 用户已修改、新包未变化：保留用户修改并报告（`PRESERVED local modification`）。
- 用户和新包都修改同一文件：**写入前停止**并报告冲突。
- 新包删除、用户修改过：保留并报告。

冲突中止不会改写 `opencode.json`、`AGENTS.md` 或受管资源；但它**会**在
`<home>/backups/` 留下本次的预升级快照（该快照正是回滚要用的）。

## 推荐给 AI 的指令

```text
请阅读本仓库的 AI_UPGRADE.md，把 ${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode} 上的
Vibe Coding OpenCode Global Core 升级到本包版本。

要求：
1. 升级前运行 preflight，并阅读现有的 AGENTS.md 与 opencode.json。
2. 复用或修复 vibe-coding Python 3.11 环境（见 AI_INSTALL.md 的“Vibe Python 环境与安装流程”）。
3. 保留用户对 AGENTS.md、opencode.json、skills/**、vibe-workflow/** 的本地修改。
4. 遇到同名文件冲突必须停止并报告，不要强制覆盖。
5. 升级后运行 verify，并报告保留的本地修改与冲突。
```

## Linux / WSL 升级

```bash
"$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")" \
  scripts/opencode_installer.py preflight
./runtime/opencode/install.sh update
./runtime/opencode/install.sh verify
```

`runtime/opencode/install.sh` 会先解析 Python 3.11+ 解释器（`VIBE_PYTHON` →
`${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python` → `python3` → `python`），
再用它执行 `scripts/opencode_installer.py`。

## 从 OpenCode V1 形态升级（只支持 OpenCode V2）

本包只支持 OpenCode **V2**（`opencode --version` 为 2.x）；preflight 检测到 1.x 会停止。`update` 会：

- 删除旧版 V1 单文件插件 `plugins/vibe-workflow.ts`（未被本地修改时），安装 V2 目录插件
  `plugins/vibe-workflow/index.ts`，并从 `opencode.json` 移除 `./plugins/vibe-workflow.ts` 注册项；
  目录插件由 OpenCode 自动发现，不再写入 `opencode.json`。
- 把安装器写入的会话 Goal 控制器 `@prevalentware/opencode-goal-plugin@0.1.51` 迁移为 `@0.1.60`
  （0.1.51 在 V2 上报 `Schema.optionalWith is not a function`，无法加载）。用户自己写的其他版本
  仍按冲突处理，需先手动对齐。
- 不再安装 `@opencode-ai/plugin` npm 依赖，并撤销旧版写入 `package.json` 的该依赖；
  `node_modules/` 留给用户自行清理。
- 把安装状态从 schema 2 自动升级到 schema 3：记录当前的可选集成选择，既有所有权全部保留，
  因此之后仍可干净卸载。schema 1 也能读入并升级。比本安装器更新的状态 schema 会被明确拒绝，
  而不是猜测处理。

曾按手工方式移植过插件的机器（例如手动创建了 `plugins/vibe-workflow/index.ts`、把旧插件改名为
`plugins/vibe-workflow.ts.v1-disabled`）：先把这些手工文件移出 `plugins/`，否则 update 会因
`pre-existing file differs from package` 在写入前停止。

## 旧格式退役

format 1（`workflow.yaml` 等文件式日志）已退役：`SUPPORTED_FORMATS` 只含 `2`，任何命令都不再
解析或写入 format 1。旧模板、旧解析分支、迁移工具与三个分步退役关口一并移除。format 1 的
历史文件完整保留、不被清理，只供人工查阅：

```text
.project-log/legacy/                        退役时的 format 1 文件与 legacy/unmapped/
.project-log/docs/archive/legacy-format1/   format 1 的文档归档
```

退役不改写任何持久化值（`store_schema` 仍为 3、各 `schema_version` 仍为 1），也不追溯改写历史。

## 平台范围

- **支持**：Linux / WSL。
- **延期**：Windows（PowerShell 5.1/7 实机矩阵未验证）。旧版文档中的 Windows Hook 章节随
  codex 交付面一并移除，OpenCode 版不使用 Hooks。
