---
name: a-session-handoff
description: Persist a compact, auditable handoff before ending, compacting, or switching sessions so work can resume in under a minute without copying the whole conversation.
license: MIT
compatibility: codex
metadata:
  stage: session-management
  output: current-session
---

# Session Handoff

更新 `.project-log/current-session.md`，至少记录：

- 当前目标、阶段和 active task；
- 已完成内容与修改文件；
- 重要 B/C 决策和依据；
- 已运行验证、证据和限制；
- open questions、阻塞和风险；
- 精确到下一条可执行动作的 next action。

只保存恢复所需事实，不复制全部聊天，不记录冗长内部推理。与 YAML 事实源冲突时明确指出，不自行裁决高优先级冲突。

同时运行 `loopctl handoff` 生成 `.project-log/loop/handoff.md`。原生 Goal 进入 paused、blocked、budget/usage limited、cleared 或 replaced 时，Project Goal 保持不变。
