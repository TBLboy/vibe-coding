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
2. 使用全局运行时的正式入口创建 format 2 项目，且不覆盖已有项目文件：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/vibe-workflow/scripts/vibe.py" --root . init
```

3. 运行校验依赖安装和项目校验；若全局运行时安装在其他目录，使用实际路径替换上述脚本路径。
4. 将本轮目标写入 `workflow.yaml`、`current-session.md` 和 `task-list.yaml` 后再推进非琐碎工作。

仅首次初始化创建 `.project-log/`。全局 Agent、Skills、Commands 和 Plugin 不应写入或共享项目业务事实。

## 按需读取

优先读取 `current-session.md`、`workflow.yaml`、活跃任务以及与当前目标相关的业务原子和决策。不要无目的加载全部历史。

## 记录分层

- format 2：`records` 保存业务原子、需求基线、决策、架构、研究、对齐、复盘与蒸馏；`evidence` 保存证据状态、覆盖范围与哈希绑定；`reviews` 保存独立复核；状态库按 Git 分支上下文隔离。
- 旧格式：`business-logic/`、`requirements/`、`research/`、`architecture/`、`tasks/`、`decisions/`、`verification/`、`alignment/`、`work-trace/`、`retrospective/`、`distillation/` 仍按 YAML 分层读取。
- `progress.md`、`current-session.md`、生成的 `handoff.md` 是面向人的摘要；format 2 的精确状态以状态库为单一事实源。
- `docs/archive/`：长 Markdown 摘要的旧段落归档位置。

## 更新纪律

- Agent 推断只能是 draft/experimental，不能冒充用户确认；
- A 级直接决定，B 级写 decision-log，C 级先询问；
- 非琐碎工作先进入 task-list；
- 未验证实现只能标记 `implemented-unverified`；
- 代码差异不能自动改写业务逻辑；
- 只记录可复核的决策摘要，不记录冗长隐性推理；
- 会话结束或压缩前更新 current-session、任务、验证和下一步。
- 原生 `/goal` 管线程执行；Project Goal 与 Loop 状态不得被原生 Goal 临时措辞反向覆盖。

## 长文档维护约定

`current-session.md` 与 `progress.md` 是面向人的长 Markdown 摘要，必须遵守以下规则，不能靠手写自觉维护：

1. **最新在最上**
   - `current-session.md`：最新一次会话写在文件最上面的会话区块，旧会话依次向下。
   - `progress.md`：按日期倒序排列，最新阶段段落位于文件顶部。
2. **头部快照**
   - 两份文档顶部都维护一个简短稳定的“当前状态”区块，每次更新时覆盖而不是追加。
   - 快照至少包含：当前任务/当前阶段、当前状态、最近一次验证、下一步（1~3 条）。
3. **超限归档**
   - `current-session.md` 超过约 50-100 KB 或会话区块达到约 10 条时，把旧会话区块移动到 `.project-log/docs/archive/`。
   - `progress.md` 超过约 50-100 KB 时，把旧阶段段落移动到 `.project-log/docs/archive/`。
   - 主文档只保留最近内容；归档文件按日期可检索，不删除任何已记录事实。
4. **单一事实源**
   - 精确当前状态与下一步以 `loop/handoff.md`、`loop/active-run.yaml` 为权威状态源。
   - 两份 md 是快速摘要，不得与权威状态互相矛盾；不要在多份长文档里各留一份不一致的“下一步”。
5. **机器维护文件边界**
   - 不手工重排或改写 `loop/events.jsonl`、`loop/active-run.yaml`、`loop/handoff.md`、`verification/evidence.yaml`。
   - 这些文件由运行时脚本与 Hooks 维护；整理长文档时只调整两个 md 的位置、做归档和改写为更清晰的结构。

详细规范见 `REFERENCE.md`、`.project-log/docs/`、模板和 schemas。
