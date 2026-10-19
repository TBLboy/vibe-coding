---
name: a-requirement-baseline
description: "Requirement baseline."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Requirement baseline

Freeze an approved requirement baseline: scope, acceptance criteria, constraints, assumptions, and open questions. Use `.vibe/requirements.md` only when the baseline needs a durable dedicated file; otherwise retain it in the Task JSON and project rules.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
