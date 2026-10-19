# Data Contracts

## 1. Session mode

Session mode is stored by the OpenCode plugin using the key:

```text
vibe-v2:session-mode:<OpenCode sessionID>
```

Value: one of `fast`, `balanced`, `strict`. Missing/invalid values mean `balanced`. The mode is not written to project progress files and is not global to all sessions in the same project.

## 2. Per-Session Task control pointer

The plugin stores a minimal active Task ID keyed by OpenCode `sessionID`. This pointer is not a second Task record and is not Project Memory; it exists only to enforce that reviewer invocation is authorized for the active Task in that Session. The Task JSON remains the canonical source of `policy`, `status`, `phase`, verification, and review verdict.

The main Agent uses `vibe_task_control` only when a persistent Task starts, resumes, pauses, closes, or needs strict review authorization. It is not called for trivial work without a Task and does not log intermediate actions.

## 3. Task persistence

A Task is one JSON file at. Its ID must be unique, path-safe, and match `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`; a timestamp plus short random suffix is a suitable generator. The same ID is used as the filename stem:

```text
.vibe/tasks/<task-id>.json
```

Do not create a Task file for trivial fast/balanced work. Strict always creates one. The shape is defined in `schemas/task.schema.json` and reflected by `runtime/core/task-machine.ts`.

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
- Project rules → root `AGENTS.md`.

Do not add a second canonical copy of the same fact to make a report look complete.
