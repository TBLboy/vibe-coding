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

初始化项目：在目标项目根目录创建 `.project-log/`（走现有 `init_project.py` 链路，不改动它），并建立或安全更新根目录 `AGENTS.md`。`AGENTS.md` 由两部分组成：

- 通用开发规则：来自本 skill 内部模板 `templates/general-rules.md`，以固定标记区块注入，幂等。
- 项目级规则：从项目根目录 `README.md` 和 `docs/` 主要说明文档凝炼提取；无文档则留空并提示用户补充。

## Trigger

用户要求“初始化项目 / 初始化该项目 / 项目初始化”时使用。子文件夹的 `AGENTS.md` 由 Codex 原生机制读取且优先级更高，本 skill 只维护项目根目录文件，不处理子文件夹。

## Workflow

1. 确认目标项目根目录。若用户未指定，用当前工作目录或最近的项目根。
2. 运行确定性脚本（脚本内部会先调用现有 `.project-log` 创建链路）：
   ```bash
   VIBE_RUNTIME="${CODEX_HOME:-$HOME/.codex}/vibe-workflow"
   python3 "$VIBE_RUNTIME/scripts/init_project_agents.py" \
     --target <project-root> [--project-rules "<项目级规则>"]
   ```
   - 若脚本不在运行时中，可在仓库内运行 `skills/a-project-init/scripts/init_project_agents.py`。
3. 判断项目级规则输入：
   - 目标根目录有 `README.md` 或 `docs/` 主要说明文档：阅读后凝炼项目级规则（架构边界、模块约定、构建/运行方式、团队约束等），通过 `--project-rules` 传入。
   - 没有可用文档：不传 `--project-rules`，脚本会写入占位提示，并向用户说明项目级规则留空、可手动补充。
4. 向用户报告结果：`.project-log` 与 `AGENTS.md` 的状态（created / injected / skipped）以及项目级规则是否留空。

## AGENTS.md 更新语义

- 目标无 `AGENTS.md`：创建文件，先写通用规则区块，再写“项目级规则”区。
- 目标已有 `AGENTS.md`：原内容一字不动保留（视为项目级规则），仅在文件最前面注入通用规则区块。
- 文件中已存在 `<!-- VIBE-PROJECT-GENERAL:BEGIN -->`：跳过注入，不重复叠加（幂等）。
- 已注入的项目不会自动跟随模板更新；修改模板后，对未注入或新建项目生效，已注入项目由用户决定是否手动同步。

## Maintenance

- 通用开发规则唯一来源：`templates/general-rules.md`。用户新增或修改通用规则时，直接修改该模板；不要在每个项目的 `AGENTS.md` 里分别改。
- 本 skill 不修改 `.project-log` 创建逻辑，只编排与调用。
