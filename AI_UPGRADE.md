# AI 升级指南（OpenCode）

适用于已经安装旧版 **Vibe Coding — OpenCode Global Core**，需要升级到 **0.6.0** 的电脑。

> 仓库根目录的 `update.sh` / `update.ps1` 与 `scripts/global_installer.py` 是 codex 面的遗留
> 入口。OpenCode 版的升级入口是 `runtime/opencode/install.sh update`。

本版本把新项目默认格式切到 format 2，并把 format 1 的退役分为“停止写入 / 停止读取 /
停止支持”三个需要用户单独确认的关口。升级前先阅读
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
`${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python` → `CODEX_HOME/vibe-python` →
`python3` → `python`），再用它执行 `scripts/opencode_installer.py`。

## 旧格式退役

format 1（`workflow.yaml` 等文件式日志）只保留只读访问；三个退役关口各自需要用户显式确认：

```text
stop-writing    停止写入 format 1（读与迁移仍可用）
stop-reading    停止读取 format 1
stop-support    停止支持 format 1
```

迁移与回退：

```bash
"$(cat "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-python")" \
  "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/vibe-workflow/scripts/vibe.py" \
  --root <项目根> migrate preview
```

`migrate apply` / `resume` / `rollback` 均为显式操作，不会自动执行。

## 平台范围

- **支持**：Linux / WSL。
- **延期**：Windows（PowerShell 5.1/7 实机矩阵未验证）。旧版文档中的 Windows Hook 适配章节
  属于 codex 面，与 OpenCode 版无关。
