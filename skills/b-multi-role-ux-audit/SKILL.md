---
name: b-multi-role-ux-audit
description: "Multi-role UX audit."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Multi-role UX audit

Audit a running web application through real workflows for relevant roles. Separate correctness defects from usability friction, give reproduction steps, and avoid changing production data unless expressly authorized.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
