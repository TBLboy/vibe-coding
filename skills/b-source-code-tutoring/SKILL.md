---
name: b-source-code-tutoring
description: "Source-level code tutoring."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Source-level code tutoring

Use when the user wants to understand source code deeply. Trace a concrete request, function, state transition, or data path through actual files. Separate confirmed runtime behavior from inference. Do not modify code unless separately requested.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
