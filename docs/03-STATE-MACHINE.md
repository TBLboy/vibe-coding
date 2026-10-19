# State Machine and Invariants

## 1. Session mode transitions

```text
new Session ──default──> balanced
balanced ──/fast───────> fast
balanced ──/strict─────> strict
fast ──────/balanced───> balanced
fast ──────/strict─────> strict
strict ────/fast───────> fast
strict ────/balanced───> balanced
```

A valid explicit mode command is the only transition trigger. The command handler queues a mode-change prompt and creates a one-time pending token. The active mode changes only when the queued prompt consumes that token, so an in-flight action is not interrupted. A bare mode command asks the main Agent to acknowledge the change only.

Mode changes do not mutate an already-started Task's frozen policy. The current Session mode applies to new work.

## 2. Task state

Business status:

- `active`
- `blocked`
- `completed`
- `cancelled`

Phase:

- `prepare`
- `implement`
- `verify`
- `review`
- `complete`

Status and phase are different dimensions. `blocked` preserves the phase at which work stopped; `resume` returns to that phase by default. Changing phase while resuming requires a recorded decision, and a blocked Task cannot resume directly to `complete`. `completed` and `cancelled` are terminal.

## 3. Valid transitions

```text
create Task
  status=active, phase=prepare, frozen policy
       ↓ begin implementation
  active / implement
       ↓ begin verification
  active / verify
       ├─ verification failed → active / implement
       └─ verification passed or justified N/A
             ├─ fast/balanced → completed / complete
             └─ strict → active / review
                           ├─ go → completed / complete
                           ├─ fixable findings → implement
                           │     → verify → review
                           └─ user decision needed / retry cap → blocked
```

Any non-terminal Task may be blocked or cancelled. A blocked Task must be resumed before normal phase transitions. Terminal Tasks cannot be reopened by a normal transition.

## 4. Reviewer repair cap

`repairRounds` starts at 0 when strict verification passes and review begins.

- First review with fixable findings: increment to 1 and return to implementation.
- Second review with fixable findings: increment to 2 and return to implementation.
- Third review still has required findings: block, report unresolved findings, and stop automatic retries. Any further attempt requires a new explicit user request.
- If the reviewer says a business/product decision is required, block immediately and ask the user.

Every repair must be followed by verification before the next review. Reviewer does not edit product code.

## 5. Invariants

1. New Session mode is `balanced`.
2. Only explicit slash commands change mode.
3. Task policy is immutable after Task start.
4. Fast and balanced never invoke reviewer and never create review records.
5. Strict Task cannot complete without reviewer verdict `go`.
6. Any completed Task has verification `passed`, or `not_applicable` with an explicit reason.
7. A strict Task has non-empty `doneWhen` acceptance criteria.
8. A failed verification returns the Task to implementation; it does not mark the Task complete.
9. A review finding invalidates the previous verification for any code that will be changed; verification must be rerun.
10. Reviewer repair loops are bounded.
11. Project Memory never receives action-level logs.
12. Invalid or unknown mode values resolve to `balanced`; invalid Task transitions fail closed.

## 6. Mode command while a Task is active

Once the queued command is processed, the Session mode changes; the currently running action is not interrupted and the Task policy is not changed. The main Agent must classify trailing text as either:

- a continuation of the current Task: keep the Task's frozen policy; or
- a new independent request: use the newly selected Session mode for the new Task/work.

Do not split a single Task into multiple policies mid-flight. Do not run more than one registered active Task per Session in the first version. Separate OpenCode Sessions have separate recovery paths and active-Task pointers; project-level `progress.md` remains shared.
