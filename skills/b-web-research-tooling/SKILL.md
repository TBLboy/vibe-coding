---
name: b-web-research-tooling
description: "Web research tooling."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Web research tooling

Gather current web evidence safely for research, troubleshooting, and fact checks. Prefer authoritative sources, preserve URLs and dates, handle secrets carefully, and distinguish source claims from conclusions.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
