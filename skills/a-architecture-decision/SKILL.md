---
name: a-architecture-decision
description: "Architecture decision."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Architecture decision

Translate approved requirements into module boundaries, interfaces, data flow, failure handling, and operational constraints. Record a material approved decision in `.vibe/progress.md`; do not create a second architecture state system.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
