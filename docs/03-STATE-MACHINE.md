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

Status and phase are different dimensions. `blocked` preserves the phase at which work stopped; `resume` returns to that phase by default. Changing phase while resuming requires a recorded decision, and a blocked Task cannot resume directly to `complete`. `completed` and `cancelled` are terminal after close. An unclosed completed Task may invalidate stale verification and return to implementation.

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

Any non-terminal Task may be blocked or cancelled. A blocked Task must be resumed before normal phase transitions. Closed Tasks cannot be reopened. Before close, stale evidence requires explicit invalidation and re-verification.

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

## 7. Runtime-owned lifecycle API (P0 repair)

Create a fresh JSON matching the schema (`active/prepare`, `not_run`, empty decisions, no review), then call `vibe_task_control` with `{action, taskID, event?}`. Once registered, **never edit the Task file directly**. Runtime transitions update the canonical JSON and a project-scoped integrity/ownership receipt in plugin storage.

| action | event / conditions |
|---|---|
| `start` | Fresh prepare record; policy equals current Session mode |
| `transition` | `{type:"begin_implementation", risk:"quick"\|"standard"\|"strict"}`; strict risk requires strict policy |
| `transition` | `{type:"record_decision", decision:"…"}` in prepare/implement |
| `transition` | `{type:"begin_verification", artifacts:["relative/path", ...]}` BEFORE checks; include requirements, test harness, dependency locks and unchanged relevant artifacts |
| `transition` | `{type:"verification_passed", summary:"…", checks:["command + result"], limitations:[]}`; optionally `status:"not_applicable"` and `notApplicableReason` for justified N/A |
| `transition` | `{type:"verification_failed", summary:"…", checks:[...], limitations:[...]}` |
| `transition` | `{type:"invalidate_verification"}` if covered artifacts changed; re-enter implementation then verify again |
| `transition` | `{type:"block", reason:"…"}` or `{type:"cancel", reason:"…"}` |
| `pause` | Blocked Task; releases Session active pointer |
| `resume` | Reclaim unclosed non-blocked Task after interruption; preserves policy and invalidates old reviewer permit |
| `resume_blocked` | `{decision:"…", phase:"implement", nextAction:"…"}` when a decision changes the plan; otherwise omit phase to resume the same phase |
| `authorize_review` | Current verified strict Task, pending verdict; one-time permit |
| `reset_review` | Invalidate interrupted or malformed pending review before requesting another permit |
| `close` | Completed Task with current evidence (strict also needs host-recorded `go`), or cancelled Task |

A fresh native `subagent` call with agent `vibe-reviewer` and no reused child `sessionID` is required. Do not require or invent a `background` option: OpenCode 2.3.0 always launches subagents in the background. Permission admission consumes the permit but does not record completion.

For a native `{sessionID,status:"running"}` result, `execute.after` binds the child ID to the exact admitted call in the existing receipt. It never accepts the launch's `output` as a verdict. At the next natural parent `context` continuation (normally after the host's background notification), Runtime reads the bound child's `session.get`/`session.context` directly. It requires matching parent, reviewer Agent and workspace, a successful terminal idle marker, and completed final reviewer assistant JSON from that child's first un-compacted turn. Reused/multi-turn, compacted, failed, interrupted, malformed or incomplete results stay pending. There is no timer, polling loop, parent-authored completion tool or copied notification verdict. An older synchronous native `status:"completed"` result remains supported through its matching `execute.after` event.

Both paths recheck still-current artifact evidence and use the same bounded review transitions. Reset, pause, resume/ownership transfer and any Task transition invalidate outstanding bindings. After a running launch, wait for the host notification without polling; pending alone is not a failure while the child is running. Read the Task on continuation; inspect a failed/malformed/stale result and reset before retrying with a fresh child. Review verdict events are not available to the main Agent.

Risk is an independent minimum, not a ceiling set by mode. Fast/balanced can use deeper tests but must not run a strict-risk implementation. Ask the user for `/strict`, cancel/close or pause the old Task as appropriate, and start a new strict Task. Runtime enforces declared strict risk at entry; correct risk classification and reclassification remain Agent duties (shell writes are not sandboxed).

Artifact evidence includes explicit relative regular files, Git HEAD and changed tracked/untracked files (excluding routine Task/session/progress memory changes from automatic collection). External services, ignored files, dependencies outside the workspace and hardware need separately reported evidence; the fingerprint is freshness, not proof of test execution. Non-Git projects require explicit coverage. Cross-worktree resume needs fresh evidence in the new workspace.

Legacy/unregistered or externally modified Task records fail closed. Preserve the old record for history, create a new ID with the same approved goal and acceptance criteria, and verify again. Do not import old verdicts. If storage fails after a file write, restore the exact last registered bytes if available or start a new ID. The receipt is not a security boundary against a hostile user with direct plugin storage access; simultaneous independent host processes are not a supported write model.
