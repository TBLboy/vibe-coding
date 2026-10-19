---
name: a-engineering-spec
description: "Engineering specification."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering specification

Create a task-specific implementation specification: affected modules, interfaces, data changes, failure behavior, tests, migration, rollout, and rollback. For persistent work, put acceptance criteria and decisions in the V2 Task JSON.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
