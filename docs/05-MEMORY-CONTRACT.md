# Project Memory Contract

## Principle

> Record facts that a future agent needs, not actions that a past agent performed.

Project Memory is not a transcript, diary, command log, event stream, or model-thought archive.

## Memory root

A project owns exactly one `.vibe/` at its top level. Sub-directories, sub-repositories and worktrees share it; never create a second `.vibe/` below it. The runtime resolves the memory root as the nearest ancestor of the Session directory that already contains `.vibe/` (falling back to the Session directory for a fresh project) and injects its absolute path into the Session context. Changing the working directory does not move the memory root. `a-project-init` refuses to create a nested `.vibe/` unless explicitly told the directory is a separate project.

## Files

```text
AGENTS.md                     Stable project rules and constraints
.vibe/sessions/<session-id>/current-session.md      Recovery snapshot only when unfinished work needs it
.vibe/progress.md              Durable project-level facts
.vibe/docs/                    Miscellaneous project documents (specs, research notes, briefs); created at initialization
.vibe/tasks/<task-id>.json     Only when a persistent Task is warranted
.vibe/requirements/<work>.md   Optional; one requirement baseline per piece of work, created only when durable business rules need one
.vibe/requirements/README.md   Index of baselines; exists only while at least one baseline exists
```

Do not create an empty optional file just because the template mentions it. Initialization creates `AGENTS.md`, `.vibe/progress.md`, `.vibe/docs/`, and the initializing Session's own `current-session.md` (initialization is the start of work); it never pre-creates `tasks/` or `requirements/`.

## docs/

Purpose: one predictable place for project documents that are not memory contracts — engineering specs, paper/research notes, context briefs, design sketches, meeting notes. Skills that produce such documents default here (`.vibe/docs/<topic>.md` or `.vibe/docs/<area>/…`) unless the user or `AGENTS.md` names another location. Nothing in `docs/` is read automatically; it carries no lifecycle rules and is never a substitute for `progress.md`, a requirement baseline, or a Task record.

## requirements/

Purpose: keep each piece of work's clarified business rules separate, versioned, and change-controlled, without mixing unrelated work in one file.

- One file per work item, named by its slug (normally the Task ID): `.vibe/requirements/<work>.md`. It owns its own `version`, `status` (`draft` / `active` / `superseded`), change log, and supersession metadata. Later work never edits another work's baseline in place.
- `README.md` is the index: one line per baseline with id, title, status, current version, and related Task IDs. Maintain it whenever a baseline is created, activated, or superseded.
- Business rules that hold across all work are not left inside a baseline; once stable, distill them into the project `AGENTS.md` project-level rules. Audits treat `AGENTS.md` plus every `active` baseline as the current business truth.
- A Task references its baseline by path in `goal`; `doneWhen` points at that baseline's acceptance criteria. The Task schema is unchanged.
- A small bounded increment whose `goal` + `doneWhen` already state the rules needs no baseline file.

## current-session.md

Purpose: recover unfinished work for one OpenCode Session after context loss or a Session boundary. Each Session has its own file under `.vibe/sessions/<URL-encoded-session-id>/current-session.md`; do not use one shared recovery snapshot for all Sessions.

Write/update the file for the current Session only when one of these is true:

- meaningful work remains unfinished and must be resumed;
- a blocker needs follow-up;
- the next action depends on a fact that would otherwise be lost.

Keep only:

- current Task ID/title if one exists;
- what is already done;
- confirmed constraints/decisions needed to continue;
- blocker, if any;
- exact next action.

When no resumable work or blocker remains, delete that Session file and its now-empty directory. Do not leave "no resumable work" stubs and do not keep a history of completed trivial Sessions; the absence of the file is the signal.

## progress.md

Purpose: understand durable project progress without replaying a transcript.

Update only when one of these changes:

- important feature/milestone completed;
- project stage materially changes;
- important business or technical decision is made;
- important limitation is discovered;
- important blocker is resolved or remaining work materially changes.

Do not add an entry for a typo fix, ordinary file edit, shell command, grep, normal retry, or test invocation by itself.

## Task file

Task records capture only durable task facts: goal, acceptance criteria, frozen policy, status/phase, material decisions, verification result, strict review result if applicable, blocker, and next action.

Do not add event arrays, tool histories, Run objects, standalone Evidence, or reviewer transcripts.

## Write decision table

| Situation | Task | current-session | progress |
|---|---|---|---|
| One-line copy change, verified and delivered | No | No | No |
| Small config fix, done in one turn | Usually no | No | No unless durable decision |
| Multi-step feature with acceptance criteria | Yes in balanced/strict; fast if persistence matters | While unfinished/recoverable | When feature/milestone completes |
| Work blocked on user decision | Yes if persistent work exists | Yes | Only if the blocker changes project-level facts |
| Important architecture decision | If tied to ongoing work | If work remains unfinished | Yes |
| Ordinary failed retry followed by success | No extra record | No | No |
| Verification reveals a material limitation | If task persists | If it affects unfinished work | Yes |

## Memory quality bar

Before writing, ask: “Would the next agent make a worse decision or lose meaningful progress if this fact were omitted?” If not, do not write it.
