---
name: b-skill-authoring
description: "V2 skill authoring."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# V2 skill authoring

Use to design a focused OpenCode Skill. Define a narrow trigger, inputs, outputs, boundaries, and verification. Skills must follow the V2 Task and Project Memory contracts.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
