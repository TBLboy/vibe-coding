---
name: a-engineering-landing
description: "Engineering landing."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Engineering landing

Implement an approved change with controlled scope, incremental validation, and honest delivery. Use V2 Task JSON only when persistence is warranted; update session/progress memory only under V2 write triggers.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
