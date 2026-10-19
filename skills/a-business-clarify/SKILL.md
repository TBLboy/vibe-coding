---
name: a-business-clarify
description: "Business clarification."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Business clarification

Turn vague intent into testable rules: actors, scenarios, states, exceptions, boundaries, and invariants. Ask one highest-impact question when product semantics are ambiguous. Put durable approved rules in `AGENTS.md` or `.vibe/requirements.md` only when warranted.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
