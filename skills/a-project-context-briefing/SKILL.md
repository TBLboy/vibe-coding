---
name: a-project-context-briefing
description: "Project context briefing."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Project context briefing

Prepare a self-contained, evidence-based brief for another agent, teammate, vendor, forum, or issue. Include confirmed facts, unknowns, constraints, reproduction, and the requested decision; never fill gaps with guesses.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
