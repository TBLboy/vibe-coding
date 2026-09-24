# Project Log v2 Reference

## File ownership

| Storage | Primary writer | Notes |
|---|---|---|
| format 2 `records` / `evidence` / `reviews` | formal `vibe` commands | Branch-local state database; exact current facts |
| ledger `ledger/v1/ledger.jsonl` | formal `vibe` commands | Git-tracked append-only ledger; the durable fact source |
| current-session.md | vibe-goal | Concise, current, resumable |
| progress.md | vibe-goal | Human-readable phase summary; reverse-chronological |
| docs/archive/ | vibe-goal | Archived old sections from current-session.md / progress.md |

Project Log format 2 is the only supported format. The retired format 1 files
(`workflow.yaml`, `task-list.yaml`, `active-goal.yaml`, …) are preserved read-only
under `.project-log/legacy/` for history and are not parsed by any command.

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

## Long markdown documents

`current-session.md` and `progress.md` are human-facing summaries, not authoritative runtime state:

- Latest on top: latest session block / phase section is at the top of the file; older sections go downward.
- Header snapshot: the short "current state" block at the top is overwritten on every update instead of appended.
- Archive on threshold: when `current-session.md` exceeds about 50-100 KB or roughly 10 session blocks, move older sections to `.project-log/docs/archive/`. Do the same for `progress.md` at about 50-100 KB.
- Single source of truth: format 2 uses the branch-local state database, the Git ledger and generated `handoff.md`. The two md files must not contradict them.
- Machine-maintained state (the format 2 database, the ledger, and generated views) must not be manually reordered or rewritten.
