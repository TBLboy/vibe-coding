---
name: b-concise-communication
description: "Switch to a persistent ultra-concise communication mode while preserving technical accuracy. Use when the user asks for caveman mode, fewer tokens, terse answers, or brief communication."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Concise Communication

## Activation

Activate when the user asks for caveman mode, terse communication, less verbosity, or fewer tokens. Keep it active until the user asks for normal detail or disables it.

## Rules

- Remove pleasantries, filler, repeated conclusions, and nonessential qualifiers.
- Prefer short accurate words, fragments, compact lists, and `cause -> effect` notation.
- Preserve exact technical terms, commands, paths, code blocks, errors, warnings, and evidence.
- State result, reason, and next action in the fewest unambiguous words.
- Concise applies to prose, not to records: Task JSON, `current-session.md`, and `.vibe/progress.md` keep their normal complete content.

## Safety Exception

Temporarily return to normal clarity for destructive operations, security warnings, irreversible confirmations, ambiguous multi-step procedures, C-level questions, or when the user asks for explanation. Resume concise mode after the critical information is clear.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
