---
name: a-project-log
description: 维护以原子业务逻辑为事实源的项目记忆、需求基线、架构、生命周期任务、决策行动结果、验证证据、三方对齐、工作留痕和会话恢复状态。
compatibility: codex
metadata:
  version: "2.0-draft"
  workflow: "vibe-goal"
---

# Project Log v2

`.project-log/` 是工作流的长期运行层，不是普通进度笔记。

## 首次初始化

在当前项目根目录找不到 `.project-log/` 时，先初始化，不能把全局工作流目录当作项目日志。

1. 确认当前工作目录是目标项目根目录。
2. 使用全局运行时脚本创建模板，且不覆盖已有项目文件：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/vibe-workflow/scripts/init_project.py" --target .
```

3. 运行校验依赖安装和项目校验；若全局运行时安装在其他目录，使用实际路径替换上述脚本路径。
4. 将本轮目标写入 `workflow.yaml`、`current-session.md` 和 `task-list.yaml` 后再推进非琐碎工作。

仅首次初始化创建 `.project-log/`。全局 Agent、Skills、Commands 和 Plugin 不应写入或共享项目业务事实。

## 按需读取

优先读取 `current-session.md`、`workflow.yaml`、活跃任务以及与当前目标相关的业务原子和决策。不要无目的加载全部历史。

## 记录分层

- `business-logic/atoms.yaml`：系统应该怎样工作；
- `business-logic/clarification.yaml`：功能业务逻辑、技术业务逻辑及双向对齐；
- `goals/active-goal.yaml`：项目级成功条件、非目标、约束和必需证据；
- `requirements/baseline.yaml`：本次增量批准了什么；
- `research/solution-research.yaml`：技术选型证据；
- `architecture/architecture.yaml`：职责、接口、数据和故障边界；
- `tasks/task-list.yaml`：当前要做什么；
- `progress.md`：面向人读的阶段进度摘要，保持与 task-list 同步；
- `decisions/decision-log.yaml`：为何这样选择及结果；
- `verification/evidence.yaml`：如何证明完成；
- `alignment/findings.yaml`：业务、代码和测试的差异；
- `work-trace/trace.yaml`：高信号思维-行动-结果链；
- `retrospective/`、`distillation/`：如何改进工作方式；
- `current-session.md`：下一次一分钟恢复。
- `loop/active-run.yaml`、`events.jsonl`、`evidence-index.yaml`、`handoff.md`：Loop 快照、历史、证据有效性和恢复视图。

## 更新纪律

- Agent 推断只能是 draft/experimental，不能冒充用户确认；
- A 级直接决定，B 级写 decision-log，C 级先询问；
- 非琐碎工作先进入 task-list；
- 未验证实现只能标记 `implemented-unverified`；
- 代码差异不能自动改写业务逻辑；
- 只记录可复核的决策摘要，不记录冗长隐性推理；
- 会话结束或压缩前更新 current-session、任务、验证和下一步。
- 原生 `/goal` 管线程执行；Project Goal 与 Loop 状态不得被原生 Goal 临时措辞反向覆盖。

详细规范见 `REFERENCE.md`、`.project-log/docs/`、模板和 schemas。
