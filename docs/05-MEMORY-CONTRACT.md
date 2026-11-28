# Project Memory Contract

## Principle

> Record facts that a future agent needs, not actions that a past agent performed.

Project Memory is not a transcript, diary, command log, event stream, or model-thought archive.

## Memory root

A project owns exactly one `.vibe/` at its top level. Sub-directories, sub-repositories and worktrees share it; never create a second `.vibe/` below it. The runtime resolves the Session workspace (Git top-level when available), prefers the canonical Git common-directory project root when it owns `.vibe/`, otherwise walks workspace ancestors for `.vibe/` (falling back to the workspace root for a fresh project), and injects its absolute path into the Session context. Changing the working directory does not move the memory root. Workbench creation and Key binding are the default; explicit offline initialization is also supported at the project root. Neither route permits nested `.vibe/` or overwrites existing memory.

## Files

```text
AGENTS.md                     Stable project rules and constraints
.vibe/sessions/<session-id>/current-session.md      Recovery snapshot only when unfinished work needs it
.vibe/progress.md              Durable project-level facts
.vibe/docs/                    Miscellaneous project documents (specs, research notes, briefs); created at initialization
.vibe/tasks/<task-id>.json     Only when a persistent Task is warranted
.vibe/requirements/<work>.md   Optional; one requirement baseline per piece of work, created only when durable business rules need one
.vibe/requirements/README.md   Index of baselines; initially empty in the canonical template
.vibe/lessons/README.md        Index of lessons (type, status, keywords, summary); initially empty in the canonical template
.vibe/lessons/<id>.md          One lesson per file
```

Workbench is the primary initializer; explicit offline initialization uses its exact published template. The engineering-dev template contains `AGENTS.md`, `.vibe/progress.md`, `.vibe/docs/.gitkeep`, `.vibe/requirements/README.md`, `.vibe/tasks/.gitkeep`, `.vibe/lessons/README.md`. No Session or Task record is fabricated. Optional records are created only when warranted. Existing logs can be imported unchanged at workspace creation. New template versions apply only to new blank initialization; never overlay, migrate or rewrite existing memory on upgrade or import.

## Knowledge quality and ownership

Write only knowledge whose absence would impair a later decision, prevent a repeated mistake, or lose meaningful progress. A useful record is accurate, independently understandable, causal where relevant, scoped, traceable and concise. State the conclusion, applicable conditions, rationale and source (user decision, requirement ID, code path/symbol, relevant revision/configuration or actual verification), as needed; distinguish confirmed facts, inference, proposal and unverified behavior. Never present a plan, static inspection or a historical passing test as current execution evidence. Do not store credentials, private device settings, raw sensitive output, model thoughts or operation logs in synced memory.

Maintain one authoritative home per fact. Summarize and link rather than duplicate; use short descriptive headings, stable IDs, repository-relative paths and meaningful keywords. No mandatory headings, new indexes, schemas, scoring or scheduled scans. Update the affected current record when durable knowledge changes, not just the progress summary. Preserve approved requirement history, Runtime-owned Task facts, user-authored material and unrelated edits. Mark superseded technical guidance as historical or replace obsolete current guidance with evidence and a reference to its successor; never silently erase conflicting or historical evidence. Re-read shared files before changing them and preserve concurrent/user edits; surface unresolved sync conflicts through existing controls, not automatic selection.

## AGENTS.md

Stable user-approved project rules, business invariants and engineering constraints only. Keep high-signal, actionable rules with scope when needed; propose changes and obtain user approval before editing AGENTS.md. No transient progress, detailed reports, tentative conclusions or wholesale lesson copies. A new user correction may invalidate a previous rule but does not authorize rewriting it silently.

## docs/

Purpose: durable technical knowledge and supporting documents — architecture rationale, engineering specs, paper/research notes, context briefs, design sketches, meeting notes. Record material mechanisms, constraints, tradeoffs, consequences and evidence, plus the conditions that would invalidate a decision. Keep current guidance distinct from proposals and history; use progress references for important documents rather than a new index. Skills that produce such documents default here (`.vibe/docs/<topic>.md` or `.vibe/docs/<area>/…`) unless the user or `AGENTS.md` names another location. Nothing in `docs/` is read automatically; retrieve relevant documents on demand. It carries no Runtime lifecycle rules and is never a substitute for `progress.md`, a requirement baseline, or a Task record.

## requirements/

Purpose: keep each piece of work's clarified business rules separate, versioned, and change-controlled, without mixing unrelated work in one file.

- One file per work item, named by its slug (normally the Task ID): `.vibe/requirements/<work>.md`. It owns its own `version`, `status` (`draft` / `active` / `superseded`), change log, and supersession metadata. Later work never edits another work's baseline in place. Supersede only approved changes, preserve old versions and update related index entries; trace affected rules, docs, Tasks, code and tests. An implementation discrepancy is not permission to rewrite a business rule.
- `README.md` is the index: one line per baseline with id, title, status, current version, and related Task IDs. Maintain it whenever a baseline is created, activated, or superseded.
- For business rules that hold across all work, once stable, propose distillation into the project `AGENTS.md` project-level rules, only with user approval. Until approved, the active baseline remains authoritative. Audits treat `AGENTS.md` plus every `active` baseline as the current business truth.
- Before registration, a Task references its baseline by path in `goal`; `doneWhen` points at that baseline's acceptance criteria. For a later change follow the registered-criteria supersession rule in `06-AGENT-CONTRACT.md`; do not edit the registered Task. The Task schema is unchanged.
- A small bounded increment whose `goal` + `doneWhen` already state the rules needs no baseline file.

## lessons/

Purpose: keep reusable experience (bug causes and fixes, user corrections) so the same mistake is not repeated.

- One file per lesson, indexed in `lessons/README.md` (id, type, status, keywords, one-line summary). Entries are independent files; the index is the only shared file.
- A reusable bug is registered first with its observed symptom and trigger/context; cause and fix are added once established. Mark unresolved causes as unknown or hypotheses. Capture preventive action, applicable conditions, evidence and useful keywords; include counterexamples or limits when material. A user's project-relevant verbal correction is recorded by the Agent automatically and the user is told afterwards; revisit affected conclusions and respect baseline/AGENTS.md approval. Do not turn a casual style request or secret into synced knowledge.
- Search the index before writing; merge genuinely similar mechanisms and accumulate distinct occurrences, not repeated mentions. Maintain the index on creation, merge or status/summary/keyword change. At 3 occurrences the Agent proposes distilling the lesson into the project `AGENTS.md`; a severe, well-supported or broadly applicable lesson can justify an earlier proposal. It never edits `AGENTS.md` without the user's decision. Mark outdated advice as superseded or correct it with evidence; do not silently discard the incident history.
- `lessons/` is part of the synced `.vibe/` tree. Nothing in it is read automatically; consult matching indexed lessons before consequential work. It is never a substitute for `progress.md`.

## current-session.md

Purpose: recover unfinished work for one OpenCode Session after context loss in that Session. Each Session has its own file under `.vibe/sessions/<URL-encoded-session-id>/current-session.md`; do not use one shared recovery snapshot for all Sessions.

Use the exact injected recovery path, never guess by timestamps or read/write another Session's recovery directory. For a new Session or device, use the user-designated Task and relevant durable knowledge; do not adopt another Session's active pointer or mutate its snapshot. Use the existing Runtime: `resume` / `resume_blocked` for registered local work; the explicit `adopt` action for eligible synced Tasks on another device, subject to its integrity and ownership checks. Recheck workspace/evidence and do not take over work still being executed elsewhere.

Write/update the current Session file only when one of these is true:

- meaningful work remains unfinished and must be resumed;
- a blocker needs follow-up;
- the next action depends on a fact that would otherwise be lost.

Keep only:

- current Task ID/title if one exists;
- what is already done;
- confirmed constraints/decisions needed to continue;
- blocker, if any;
- exact next action and the relevant file/contract references.

Read back enough to resume without replaying the conversation; refresh it at meaningful interruption/checkpoint when recovery information changes, including before a known native compaction if necessary. After context loss, consult the injected root, exact current Session recovery path and registered Task, reconcile actual worktree changes, constraints, decisions, verification and next action before acting. A summary is navigation, not authority or proof of completion. Do not create a second snapshot or force writes for a trivial task. Do not copy whole documents or claims of completion unsupported by the Task.

When no resumable work or blocker remains, delete that Session file and its now-empty directory. Do not leave "no resumable work" stubs and do not keep a history of completed trivial Sessions; the absence of the file is the signal.

## progress.md

Purpose: understand the current project state without replaying a transcript. Keep the current stage, completed capabilities/milestones, still-effective decisions, known limitations/unverified areas and important remaining work easy to find. Link the authoritative requirements, docs or Task only where useful. Merge or replace stale summaries when the project changes; retain only history with future value and distinguish it from current state. No required new section or directory.

Update only when one of these changes:

- important feature/milestone completed;
- project stage materially changes;
- important business or technical decision is made;
- important limitation is discovered;
- important blocker is resolved or remaining work materially changes.

Do not add an entry for a typo fix, ordinary file edit, shell command, grep, normal retry, or test invocation by itself.

## Task file

Task records capture only durable task facts: goal, acceptance criteria, frozen policy, status/phase, material decisions, verification result, strict review result if applicable, blocker, and next action.

Registered Task state and criteria are Runtime-owned; never edit JSON directly after registration. Reference durable knowledge rather than copying it; preserve verification scope and limitations. Do not add event arrays, tool histories, Run objects, standalone Evidence, or reviewer transcripts.

## Write decision table

Examples assume fast/balanced unless specified; strict engineering implementation and engineering work needing durable tracking require a Task; ordinary consultation without durable tracking needs does not.

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

Before writing, ask: “Would the next agent make a worse decision or lose meaningful progress if this fact were omitted?” If not, do not write it. Capture material decisions, corrections and recovery facts when they become known, not only at delivery; use the correct owner and permission boundary. At a meaningful checkpoint or completion, reconcile changed facts and references, remove stale summaries, and preserve unresolved gaps rather than claiming certainty. Do not create memory for trivial completed work just for ceremony. The helper `runtime/core/memory-policy.ts` expresses write triggers; actual Markdown judgment and I/O belong to the Agent, not an automatic Runtime writer.

## Relevant memory consumption

Start with project rules, actual task intent and the injected root/Task/recovery facts. When project context matters, read progress for orientation, then select relevant active requirements, docs and indexed lessons by domain, path, symbol, failure mechanism or keyword; open only useful source records and follow references as needed. Missing optional memory is not an error. For a simple edit, no unrelated retrieval or write is necessary. For unfamiliar work, consequential decisions or recurrence-prone defects, consult applicable knowledge before committing to a solution. Do not auto-inject all memory, invent missing facts, or add a mandatory retrieval stage.

Use authority by claim, not a blanket file ranking: user-approved project rules and active baselines define intended behavior; current code/config and actual observations establish implementation; Runtime Task records establish task state and verification at its recorded scope/revision; docs, lessons and progress provide context that may be stale. Validate applicability against current source, revision, configuration and evidence. When intent and implementation disagree, identify the gap and resolve through existing authority; do not silently pick one or treat history as permission. Correct affected current knowledge when supported and authorized, preserving history and unresolved uncertainty. Never auto-resume another Session or let memory override frozen Policy, sync safeguards or current user authority.
