---
name: a-codebase-onboarding
description: Onboard an existing codebase by mapping architecture, current observable behavior, tests, data, integrations, and risks without treating code behavior as automatically authoritative business logic.
license: MIT
compatibility: codex
metadata:
  stage: onboarding
  output: evidence-map
---

# Codebase Onboarding

## Purpose

建立“系统现在如何工作”的证据地图，为业务澄清、对齐和任务规划提供起点，而不是把旧代码批量写成正式业务规范。

## Procedure

1. 从用户目标限定分析范围；不做无边界全仓扫描。
2. 识别语言、入口、构建、模块、数据存储、部署、外部集成和测试。
3. 提取当前可观察行为、状态、错误、配置、隐含契约和关键路径。
4. 标注证据等级：正式资料、测试、代码、配置、注释或推断。
5. 形成候选业务原子，默认 `draft` / `inferred` / `evidence-derived`。
6. 双向检查当前行为与已有业务记录，分类差异。
7. 创建后续澄清、测试补齐、规格化、修复或研究任务。

## Outputs

- 架构与关键路径摘要；
- 候选业务原子；
- 高风险和知识盲区；
- 对齐 findings；
- 首批 Task List。

不得直接修改产品代码。
