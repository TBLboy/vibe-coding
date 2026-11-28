# Data Contracts

## 1. Session mode

Session mode is stored by the OpenCode plugin using the key:

```text
vibe-v2:session-mode:<OpenCode sessionID>
```

Value: one of `fast`, `balanced`, `strict`. Missing/invalid values mean `balanced`. The mode is not written to project progress files and is not global to all sessions in the same project.

## 2. Per-Session Task control pointer

The plugin stores a minimal active Task ID keyed by OpenCode `sessionID`. This pointer is not a second Task record. A separate project-scoped integrity receipt stores owner, frozen policy, Task JSON digest, closed flag and pending reviewer call identity (including the bound child Session ID after a background launch). It stores no transcript, duplicate business goal, verdict payload or verification content. The Task JSON remains the canonical source of `policy`, `status`, `phase`, verification, and review verdict.

The main Agent creates a fresh prepare record, then uses `vibe_task_control` for all registered lifecycle changes. Runtime owns subsequent writes (see state machine API). It is not called for trivial work without a Task and does not log intermediate actions.

## 3. Task persistence

A Task is one JSON file at. Its ID must be unique, path-safe, and match `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`; a timestamp plus short random suffix is a suitable generator. The same ID is used as the filename stem:

```text
.vibe/tasks/<task-id>.json
```

Do not create a Task file for trivial fast/balanced work or ordinary consultation without durable tracking needs in any mode. Strict engineering implementation and engineering work needing durable tracking require one. The shape is defined in `schemas/task.schema.json` and reflected by `runtime/core/task-machine.ts`.

Required fields:

- `id`, `title`, `goal`, `doneWhen`
- `policy` (immutable after start)
- `status`, `phase`
- `decisions`
- `verification`

Optional fields:

- `review` — strict only, nested inside the Task; never a separate review record
- `blocker`, `cancelReason`, `nextAction`

## 4. Verification result

`verification.status` is one of:

- `not_run`
- `passed`
- `failed`
- `not_applicable`
- `blocked`

`not_applicable` requires a clear reason. Do not use it merely because a test is inconvenient. `checks` contains concise check names/results, not full shell transcripts. `limitations` contains material unverified areas only.

## 5. Review result

Review exists only after a strict Task reaches review phase. It is nested in the Task:

```json
{
  "verdict": "pending",
  "findings": [],
  "repairRounds": 0
}
```

Final reviewer verdict is `go`, `conditional`, or `no-go`. A `go` result has no required-change findings; `conditional` and `no-go` must include at least one. Each finding is an object with `severity`, `requirement`, `location`, `problem`, and `requiredChange`. Findings must be tied to an explicit requirement and an observable problem. No empty review record is created for fast/balanced.

## 6. Canonical facts

- Current Session mode → plugin storage.
- Task execution state and acceptance criteria → Task JSON.
- Current unfinished work needed for recovery → `.vibe/sessions/<session-id>/current-session.md` (Session-scoped; exact path is injected by the plugin).
- Durable project milestones/decisions/limitations → `.vibe/progress.md` and project-specific source docs when appropriate.
- Project rules → root `AGENTS.md` (user-approved).
- Approved durable business rules → active per-work requirements; technical rationale → relevant docs; reusable experience → indexed lessons. See `05-MEMORY-CONTRACT.md` for scope, maintenance and claim-specific authority.

Do not add a second canonical copy of the same fact to make a report look complete.

## Evidence freshness

`verification.evidence` is a Runtime-created object with `root`, `paths`, `digest` (SHA-256), and Git HEAD incorporated in the digest. This is part of the Task, not a standalone evidence store. Legacy records remain readable but are not trusted for resume or close without a receipt.
