---
name: a-project-init
description: "Initialize a new project with the minimal V2 rules and memory layout."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# V2 Project Initialization

Use when the user asks to initialize, set up, or bootstrap a project for Vibe Coding V2.

## Initialization contract

Work from the project root and make the smallest idempotent change:

1. If `AGENTS.md` is missing, create it from the V2 project-rules template. If it exists, read it and preserve its content; never overwrite user rules.
2. Create `.vibe/progress.md` only when missing, with a short empty-project heading and no invented facts.
3. Create `.vibe/sessions/<current-session-id>/current-session.md` only when missing. Use the exact OpenCode Session ID supplied by the runtime, URL-encoded as required by the V2 contract; never use a shared placeholder or another Session's directory.
4. Do not create `.vibe/tasks/` until a persistent Task is actually warranted.
5. Do not create `.vibe/requirements.md` unless durable business requirements need a dedicated baseline.

After initialization, read `AGENTS.md` and report the created/preserved files. If the user supplied a project-specific rule, add only that rule to `AGENTS.md`; do not fill the file with generic framework text already provided by V2.

## Safety and verification

- Never replace, truncate, or delete an existing `AGENTS.md`, `.vibe/progress.md`, or Session snapshot.
- Keep initialization idempotent: a second run should report that existing files were preserved and make no duplicate content.
- Verify the expected files exist and that the Session snapshot is under the current Session's encoded path.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above.
- Report confirmed facts, assumptions, verification performed, and material limitations.
