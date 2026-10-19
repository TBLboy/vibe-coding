---
name: b-opencode-model-config
description: "OpenCode model configuration."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# OpenCode model configuration

Use for an existing provider’s model context-window or image-input declarations. Read effective model state first; preserve output limits; use modalities rather than legacy attachment; verify the live model list after editing. Never print API keys or change provider credentials. Record a durable configuration decision in `.vibe/progress.md` only when it materially affects future work.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Do not create or write `.project-log`, Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.
- Report confirmed facts, assumptions, verification performed, and material limitations.
