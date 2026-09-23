---
name: a-project-log-align
description: Align a work folder's .project-log with the archived copy in the knowledge base, merging the Git ledger and rebuilding the local SQLite projection. Use when moving to a new machine, resuming a project whose logs live in the knowledge base, or syncing a pulled archive into the current work folder.
license: MIT
compatibility: opencode
metadata:
  type: tool-skill-pack
  output: aligned-project-log-and-rebuilt-sqlite
---

# Project Log Align

Merge this work folder's `.project-log/` with the archived copy in the knowledge base,
then rebuild the local SQLite projection from the merged ledger.

## When to Use

The user asks to align project progress, restore project logs on a new machine, pull
an archive into the current work folder, or "对齐项目进度".

This is the inverse of `a-project-log-archive`:

```text
archive:  work/.project-log  →  knowledge base
align:    knowledge base     →  work/.project-log  →  local SQLite
```

## First Run — Path Setup

The knowledge base path comes from, in order:

1. `--kb` on the command line;
2. this skill's `scripts/kb_path.conf`;
3. `a-project-log-archive`'s `scripts/kb_path.conf` (the archive skill owns the setting);
4. `VIBE_KB_PATH` in the environment.

If none is set, the script reports the missing config and stops.

## What It Does

1. Resolve the knowledge base root and locate `<kb>/工程记录/<work-folder-name>/.project-log/`.
   A missing copy is a hard error, never a silent no-op.
2. Verify the archived `project_id` matches the local `state-format.json`.
3. Merge the two ledgers by `command_id`: the archived commands keep their order and
   the local-only commands are appended, then the hash chain is re-sealed. Local
   commands are never dropped or reordered.
4. Copy archived `docs/` files that are missing locally; never overwrite a local doc.
5. Replay the merged ledger into the local SQLite with `vibe state-attach`, then run
   `vibe validate` and report the result.

## Execution

```bash
python3 "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/a-project-log-align/scripts/align.py" \
  --project-root <work-folder-path>
```

Use `--dry-run` to preview the merge without writing, and `--no-attach` to stop after
merging the ledger.

## Git Worktrees Are Separate Work Folders

A branch switch never hides or forks the Project Log: one work folder has one
`.project-log`, regardless of branch. `git worktree add` is different — it creates a
**separate work folder**, and the framework treats it that way. The behaviour below is
fixed by `tests/test_cross_platform_surface.py` (including the ledger-graft rejection):

- **Shared:** every worktree of one repository sees the same `project_id` and the same
  Git-tracked `.project-log` contents, including `.project-log/ledger/v1/ledger.jsonl`.
- **Not shared:** the local SQLite store lives under that worktree's own git dir
  (`git rev-parse --absolute-git-dir` is per worktree), so `context_id` differs. In a
  fresh worktree `vibe status` fails with `missing_store` until `vibe state-attach`
  replays the committed ledger.
- **Isolated writes:** each worktree carries its own working copy of the ledger. A write
  in one is not visible in the other until an explicit attach/reconcile; grafting one
  ledger over the other fails closed with `ledger_diverged`.
- **Exchange locks are per worktree:** Git's index lock does not span worktrees, so each
  worktree publishes its own pointer. Two exports across worktrees are therefore expected
  to be independent rather than serialised by the exchange lock — the tests verify
  independence, not concurrency.

Treat a worktree as a separate work folder: run `vibe state-attach` after entering a new
one, and do not let two worktrees write the same logical log while expecting an automatic
merge.

## Safety

- Never deletes a local command; the merge is a union by `command_id`.
- Refuses when the two `project_id`s differ.
- Refuses when the knowledge base has no copy of this project.
- Never touches the knowledge base; it is read-only for this skill.
- Does not overwrite local `docs/` files; conflicting docs are reported for manual review.
