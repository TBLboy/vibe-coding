---
description: Initialize or start a Vibe Coding project
agent: vibe-main
---

执行 Vibe Coding 启动流程。先读取当前项目规则和事实源；若无 `.project-log/`，使用 `a-project-init` 初始化 format 2，再建立最小 Goal/Run/Task 记录。

用户请求：$ARGUMENTS

不要只报告初始化结果；继续处理用户请求，除非用户明确只要求初始化。
