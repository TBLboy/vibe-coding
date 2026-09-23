---
description: Show the authoritative Vibe Coding project state
agent: vibe-main
---

读取 `.project-log` 的权威状态库或旧格式状态源，报告当前 Project Goal、任务、Run、阻塞、最近有效证据与精确下一步。会话 Goal 属于插件控制面而非权威状态，报告时必须与 Project Goal 分开，且不得把插件状态当作完成依据。会话 Goal 控制面是固定版本的 `@prevalentware/opencode-goal-plugin@0.1.51`（`/goal`、`/pause_goal`、`/resume_goal`）；找不到它时报告为插件缺失，而不是声称本客户端没有会话 Goal 能力。

用户请求：$ARGUMENTS
