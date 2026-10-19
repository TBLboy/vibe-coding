---
name: a-task-decompose
description: "Task decomposition."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Task decomposition

Split an approved goal into dependency-aware, vertically sliced, independently verifiable Tasks. Create V2 Task JSON only for slices needing durable tracking; avoid Goal/Run graphs and do not manufacture ceremony.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
