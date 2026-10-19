---
name: a-business-code-align
description: "Business-code alignment."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Business-code alignment

Audit business rules, implementation, configuration, and tests in both directions. Classify missing implementation, missing test, drift, conflict, or unknown. Never let current code silently redefine business requirements.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
