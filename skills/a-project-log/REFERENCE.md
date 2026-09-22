# Project Log v2 Reference

## File ownership

| Storage | Primary writer | Notes |
|---|---|---|
| format 2 `records` / `evidence` / `reviews` | formal `vibe` commands | Branch-local state database; exact current facts |
| legacy YAML files | `loopctl` migration window | Read-only compatibility; migrate explicitly |
| current-session.md | vibe-goal | Concise, current, resumable |
| progress.md | vibe-goal | Human-readable phase summary; reverse-chronological |
| docs/archive/ | vibe-goal | Archived old sections from current-session.md / progress.md |

The legacy table below describes files that remain readable in the migration window:

| File | Primary writer | Notes |
|---|---|---|
| workflow.yaml | vibe-goal | Phase changes require gate evidence |
| business-logic/atoms.yaml | business-clarify / vibe-goal | Active semantics cannot be changed from code alone |
| requirements/baseline.yaml | requirement-baseline | Versioned; supersede rather than overwrite history |
| tasks/task-list.yaml | vibe-goal / task-decompose | Every status change should preserve verification integrity |
| decisions/decision-log.yaml | any decision-making Skill | B and C decisions should be recorded |
| research/solution-research.yaml | solution-researcher | Evidence date and conditions required |
| architecture/architecture.yaml | architecture-decision | Reference supporting business atoms and decisions |
| specs/* | engineering-spec | One spec per non-trivial task or coherent group |
| alignment/findings.yaml | vibe-goal after read-only audit | Reviewer returns draft; primary decides repair/escalation |
| retrospective/retrospective.yaml | retrospective | Evidence-backed improvement only |
| distillation/candidates.yaml | operator-distill | Staged promotion; never silently update global assets |

## Fact priority

1. current user-confirmed decisions;
2. active requirement baseline;
3. active business atoms;
4. active decisions;
5. acceptance evidence;
6. code/config;
7. inference.

## Safe update patterns

- append new IDs; do not reuse IDs;
- supersede records instead of mutating history invisibly;
- use `draft`, `experimental`, or `conflict` when certainty is insufficient;
- write paths relative to the project root;
- preserve evidence and limitations;
- after edits run the validator.

## Large project scaling

When a single YAML file becomes difficult to maintain, split by domain while retaining an index file. Do not split prematurely. The validator can later be extended to resolve domain indexes.

## Long markdown documents

`current-session.md` and `progress.md` are human-facing summaries, not authoritative runtime state:

- Latest on top: latest session block / phase section is at the top of the file; older sections go downward.
- Header snapshot: the short "current state" block at the top is overwritten on every update instead of appended.
- Archive on threshold: when `current-session.md` exceeds about 50-100 KB or roughly 10 session blocks, move older sections to `.project-log/docs/archive/`. Do the same for `progress.md` at about 50-100 KB.
- Single source of truth: format 2 uses the branch-local state database and generated `handoff.md`; legacy uses `loop/handoff.md` and `loop/active-run.yaml`. The two md files must not contradict them.
- Machine-maintained state (format 2 database; legacy `loop/events.jsonl`, `loop/active-run.yaml`, `loop/handoff.md`, `verification/evidence.yaml`) must not be manually reordered or rewritten.
