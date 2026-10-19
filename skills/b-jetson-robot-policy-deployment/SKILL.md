---
name: b-jetson-robot-policy-deployment
description: "Jetson robot-policy deployment."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Jetson robot-policy deployment

Use only for requested NVIDIA Jetson robot policy deployment/review. Cover model export, runtime, sensor/action adapters, controller safety, staged validation, rollback, and hardware limits. Treat unsafe actuation or irreversible deployment as a user decision.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
