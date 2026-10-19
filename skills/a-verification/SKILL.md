---
name: a-verification
description: "Verification."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Verification

Verify changed behavior against acceptance criteria using proportional tests or targeted checks. State exact commands/results and limitations. Update the Task verification object when a persistent Task exists; do not create standalone Evidence records.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
