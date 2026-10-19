# Architecture

## 1. Four concepts

### Session

The user-facing OpenCode conversation. Owns the current selected mode and current recovery pointer. Mode is persisted per OpenCode session ID by the plugin.

### Policy

One of `fast`, `balanced`, or `strict`. Policy determines how much process is required. It does not select a separate workflow implementation.

### Task

An optional durable work unit created only when persistence/recovery is useful, except strict where it is mandatory. A Task snapshots its policy at start and keeps it until completion/cancellation.

### Project Memory

A small set of human-readable project facts: project `AGENTS.md`, optional requirements/decision notes, `.vibe/sessions/<session-id>/current-session.md`, `.vibe/progress.md`, and task files when needed. It is not a transcript.

## 2. Runtime boundaries

```text
OpenCode Session
  ├─ mode commands (/fast, /balanced, /strict)
  ├─ current mode injected into each model context
  └─ main Agent
       ├─ optional Task persistence
       ├─ implementation + risk-appropriate verification
       └─ strict only → read-only reviewer subagent

Project files
  ├─ AGENTS.md
  └─ .vibe/
       ├─ sessions/<session-id>/current-session.md (only if recovery is needed)
       ├─ progress.md          (only if durable facts changed)
       └─ tasks/<task-id>.json (only when a Task exists)
```

The plugin owns Session mode commands/injection, a minimal per-Session active-Task pointer, and the strict-review permission gate. It does not run an independent project state service, watch every tool call, write project logs, or maintain an operation ledger.

## 3. What is not a first-class concept

- **Run:** an OpenCode/model invocation is a host/runtime detail, not a project state object.
- **Goal:** product goals are ordinary requirements/project facts, not a runtime object or gate.
- **Evidence:** verification output is a field inside the Task or a concise completion summary; no standalone evidence graph.
- **Reviewer:** a phase available only to strict Tasks, not a global step or independently configurable subsystem.
- **Ledger/projection:** no event sourcing, SQLite projection, or dual source of truth.

## 4. Persistence

Use plain files. There is no database in V2 baseline.

- Session mode and active-Task pointer: OpenCode plugin storage keyed by `sessionID`; the Task JSON remains the canonical source of Task policy/status.
- Task: one JSON file per persistent Task.
- Current session: one Session-specific Markdown recovery snapshot, written only while work needs recovery.
- Progress: one Markdown project-facts summary, updated only on meaningful durable changes.
- Project rules: root `AGENTS.md`.

No fact should be duplicated across several files without a clear reason. If a Task file contains the detailed acceptance criteria and verification, `progress.md` should summarize the durable outcome rather than copy the Task.

## 5. Dependency policy

The default baseline has no third-party runtime integration, MCP, Goal plugin, database, or package dependency beyond the OpenCode plugin API provided by the host. Any later integration is opt-in and requires a concrete use case, version pin, permission review, and integration test.

## 6. Error boundaries

- A mode storage read that is absent or invalid defaults to `balanced`.
- A plugin failure must be visible; do not silently claim mode switching works if storage failed.
- Missing optional project memory is not a fatal error; create it only when useful.
- Invalid Task transitions must fail closed rather than mark the Task complete.
- Reviewer failure or unavailable reviewer in strict mode must not silently bypass the review gate.
- Verification environment failure must be reported; never fabricate a pass.
