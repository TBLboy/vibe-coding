---
name: a-codebase-onboarding
description: "Onboard an existing codebase by mapping architecture, current observable behavior, tests, data, integrations, and risks without treating code behavior as automatically authoritative business logic."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Codebase Onboarding

## Purpose

建立“系统现在如何工作”的证据地图，为业务澄清、对齐和任务规划提供起点，而不是把旧代码批量写成正式业务规范。

## Procedure

1. 从用户目标限定分析范围；不做无边界全仓扫描。
2. 识别语言、入口、构建、模块、数据存储、部署、外部集成和测试。
3. 提取当前可观察行为、状态、错误、配置、隐含契约和关键路径。
4. 标注证据等级：正式资料、测试、代码、配置、注释或推断。
5. 形成候选业务原子，默认标记为 `draft` / `inferred` / `evidence-derived`；不得直接视为已确认规则。
6. 双向检查当前行为与已有业务记录（`AGENTS.md`、`.vibe/requirements.md`、`.vibe/progress.md`），分类差异（finding 类型见 `a-business-code-align`）。
7. 列出后续澄清、测试补齐、规格化、修复或研究工作；仅在需要持久跟踪时创建 Task JSON。

## Outputs

- 架构与关键路径摘要；
- 候选业务原子（带证据等级）；
- 高风险和知识盲区；
- 对齐 findings；
- 首批后续工作清单。

持久化只写有长期价值的事实：架构约束与关键限制进入 `.vibe/progress.md`；稳定、可执行的项目规则进入 `AGENTS.md` 的项目级规则。不得直接修改产品代码。

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
