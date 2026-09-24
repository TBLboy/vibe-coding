---
name: a-session-handoff
description: Persist a compact, auditable handoff before ending, compacting, or switching sessions so work can resume in under a minute without copying the whole conversation.
license: MIT
compatibility: opencode
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

更新 `current-session.md` 时遵守 `a-project-log` 的长文档约定：

- **最新在最上**：把本次会话写成文件最上面的会话区块，旧会话区块保持在下。
- **头部快照**：覆盖更新顶部“当前状态”区块，不追加旧版本；快照包含当前阶段/任务、状态、最近验证和下一步（1~3 条）。
- **超限归档**：文件超过约 50-100 KB 或会话区块达到约 10 条时，把旧区块移到 `.project-log/docs/archive/`，不删除任何记录。
- **单一事实源**：精确下一步以状态库生成的 `handoff.md` 与 Git 账本为准；不手工重排机器维护的结构化状态文件。

同时运行 `vibe render`（或在 `vibe task handoff --task-id <TASK> --next-action <ACTION>` 后由 `vibe render` 刷新）生成 `.project-log/.state/**/generated/handoff.md`。Handoff 只记录 Project Goal、Task 与 Run 状态；Project Goal 不因会话状态变化而改变。OpenCode 的会话 Goal 由插件控制面提供，不进入 Handoff 的权威字段。
