# AI 升级指南

适用于已经安装旧版 Vibe Coding Codex Global Core，需要升级到 0.4.1 的电脑。

## 升级保证

- 安装前自动创建时间戳备份。
- 支持读取旧版 `vibe-workflow/installation-state.json`。
- 旧 runtime 和 Skill 整树未修改时，可自动迁移到逐文件升级状态。
- 用户本地修改不会被静默覆盖。
- 项目 `.project-log/` 不参与全局升级和卸载。

## 推荐给 AI 的指令

```text
请把当前电脑上的旧版 Vibe Coding Codex Global Core 升级到这个安装包版本。

要求：
1. 阅读 README.md、AI_UPGRADE.md 和新的 v0.11 执行基线。
2. 检查 CODEX_HOME、现有 AGENTS.md、config.toml、vibe-workflow 和 Skill 根目录。
3. 运行 codex update（仅当公司策略允许），然后运行 codex --version、codex doctor、codex features list。
4. Windows 使用 py -3，安装 Python 依赖。
5. 先运行 global_installer.py preflight，再运行 update。
6. 默认 --access-profile keep-existing。
7. 默认保留此前已启用的可选 MCP；如需新增 CodeGraph，使用 `--mcp codegraph`；公司网络受限时使用 --without-mcp。
8. 如果安装器报告冲突，停止并逐文件比较：旧包基线、用户当前文件、新包文件。未经确认不得覆盖用户修改。
9. 升级后运行 verify、全部单元测试和临时项目 smoke test。
10. 报告备份路径、升级文件、保留文件、冲突、验证结果和回滚命令。
```

## Windows 升级

在新安装包目录运行：

```powershell
py -3 -m pip install -r runtime\scripts\requirements.txt
py -3 scripts\global_installer.py preflight
.\update.ps1
py -3 scripts\global_installer.py verify
```

## Linux/macOS 升级

```bash
python3 -m pip install -r runtime/scripts/requirements.txt
python3 scripts/global_installer.py preflight
./update.sh
python3 scripts/global_installer.py verify
```

## 冲突含义

### 自动升级

```text
当前文件 = 上次安装版本
新包文件发生变化
```

安装器更新文件。

### 保留本地修改

```text
当前文件被用户修改
新包文件与上次版本相同
```

安装器保留当前文件，在验证输出中标记 `PRESERVED local modification`。

### 必须人工合并

```text
当前文件被用户修改
新包文件也发生变化
```

安装器在任何文件写入前停止，并报告 `Upgrade conflicts detected before writing`。

AI 应：

1. 找到安装器输出中的冲突文件。
2. 从备份或旧发布包取得旧基线。
3. 比较旧基线、用户当前文件和新包文件。
4. 保留用户有效修改，合并新规则。
5. 重新运行 update。

## 升级后检查

确认：

- 全局 `AGENTS.md` 中只有一个 Vibe managed block。
- `config.toml` 中只有一个 Vibe config block。
- `a-loop-control` 可发现。
- `roles.json` 的 8 个角色都能渲染。
- `.opencode` command/agent 校验已不存在。
- `loopctl validate` 通过。
- 原生 `/goal` 是唯一 continuation 控制器。
- Stop Hook 未安装。

## 回滚

每次安装或升级都会输出备份目录。可选 MCP 配置也应先确认 `codex mcp list`，若升级后需要回到升级前状态，优先让 AI：

1. 记录当前冲突和修改。
2. 运行卸载器移除当前版本受管资产。
3. 从升级命令输出的备份目录恢复旧 runtime、Skills、`AGENTS.md` 和 `config.toml`。
4. 运行旧版 verify。

不要通过删除真实项目 `.project-log` 回滚全局安装。
