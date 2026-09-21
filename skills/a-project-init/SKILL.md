---
name: a-project-init
description: Initialize a new or existing project by creating .project-log through the existing chain and establishing or safely updating the root AGENTS.md with the managed general development rules and project-specific rules.
license: MIT
compatibility: codex
metadata:
  stage: project-init
  output: initialized-project
---

# Project Init

## Purpose

初始化项目：在目标项目根目录通过正式 `vibe init` 入口创建 format 2 的 `.project-log/`，并建立或安全更新根目录 `AGENTS.md`。`AGENTS.md` 由两部分组成：

- 通用开发规则：来自本 skill 内部模板 `templates/general-rules.md`，以固定标记区块注入，幂等。
- 项目级规则：从项目根目录 `README.md` 和 `docs/` 主要说明文档凝炼提取；无文档则留空并提示用户补充。

## Trigger

用户要求“初始化项目 / 初始化该项目 / 项目初始化”时使用。子文件夹的 `AGENTS.md` 由 Codex 原生机制读取且优先级更高，本 skill 只维护项目根目录文件，不处理子文件夹。

## Workflow

1. 确认目标项目根目录。若用户未指定，用当前工作目录或最近的项目根。
2. 检查目标目录的 Git 状态：
   - 运行 `git -C <project-root> rev-parse --is-inside-work-tree` 判断目标是否已在 Git 仓库中。
   - 不在任何 Git 仓库中：询问用户是否需要初始化 Git 仓库；用户同意才执行 `git init`，不要未经确认就初始化。
   - 已在 Git 仓库中（含刚初始化的仓库）：询问用户该仓库属于“个人仓库”还是“团队协作仓库”，得到明确答复后再继续。
3. 运行确定性脚本（脚本内部会调用默认 format 2 的 `.project-log` 创建链路）：
   ```bash
   VIBE_RUNTIME="${CODEX_HOME:-$HOME/.codex}/vibe-workflow"
   python3 "$VIBE_RUNTIME/scripts/init_project_agents.py" \
     --target <project-root> [--project-rules "<项目级规则>"]
   ```
   - 若脚本不在运行时中，可在仓库内运行 `skills/a-project-init/scripts/init_project_agents.py`。
4. 判断项目级规则输入：
   - 目标根目录有 `README.md` 或 `docs/` 主要说明文档：阅读后凝炼项目级规则（架构边界、模块约定、构建/运行方式、团队约束等），通过 `--project-rules` 传入。
   - 没有可用文档：不传 `--project-rules`，脚本会写入占位提示，并向用户说明项目级规则留空、可手动补充。
5. 记录仓库类型（个人/团队协作）到根目录 `AGENTS.md`，并报告结果：`.project-log` 与 `AGENTS.md` 的状态（created / injected / skipped）、仓库类型、项目级规则是否留空。

## AGENTS.md 更新语义

- 目标无 `AGENTS.md`：创建文件，先写通用规则区块，再写“项目级规则”区。
- 目标已有 `AGENTS.md`：原内容一字不动保留（视为项目级规则），仅在文件最前面注入通用规则区块。
- 文件中已存在 `<!-- VIBE-PROJECT-GENERAL:BEGIN -->`：跳过注入，不重复叠加（幂等）。
- 仓库类型是项目级信息，写入“项目级规则”区：
  - 脚本新建 `AGENTS.md` 时，把 `仓库类型：个人仓库|团队协作仓库` 与其他项目规则合并后通过 `--project-rules` 传入。
  - 脚本返回 `injected` / `skipped`（文件已存在）时，由 Agent 在“项目级规则”区末尾追加或更新该行；已存在则不重复。
- 已注入的项目不会自动跟随模板更新；修改模板后，对未注入或新建项目生效，已注入项目由用户决定是否手动同步。

## Maintenance

- 通用开发规则唯一来源：`templates/general-rules.md`。用户新增或修改通用规则时，直接修改该模板；不要在每个项目的 `AGENTS.md` 里分别改。
- 本 skill 不修改 `.project-log` 创建逻辑，只编排与调用；新建项目默认生成 format 2，存量旧格式通过 `vibe migrate` 显式迁移。
