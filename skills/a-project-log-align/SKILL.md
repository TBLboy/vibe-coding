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

## The Work Folder Must Not Be a Git Repository

A Project Log lives in a **plain work folder**: the work folder itself is not a Git
repository, and it does not sit inside one. Code repositories are its *children*:

```text
work/                  plain directory, no .git here
  .project-log/        plain directory
  repo-a/.git/         repositories live below the work folder
  repo-b/.git/
```

The framework refuses any other layout, so `vibe init` never silently creates a log
in an unsupported place:

- `vibe init` in a Git worktree root — or in a directory inside one — fails with
  `unsupported_work_layout` **before writing anything**, and the error states the
  expected shape above.
- `validate_project.py` reports a log that drifted into a Git root as a validation
  failure, so a directory copy or a manual move is caught.

Because there is exactly one `.project-log` in the work folder, it covers every
repository and every branch below it, and a branch switch never hides or forks it.
Remote durability does **not** come from the work folder being a Git repository; it
comes from the knowledge-base archive, which is what `a-project-log-archive` writes
and this skill reads back.

If you need two independent logs, use two work folders — not two branches or two
worktrees of one repository.

## Safety

- Never deletes a local command; the merge is a union by `command_id`.
- Refuses when the two `project_id`s differ.
- Refuses when the knowledge base has no copy of this project.
- Never touches the knowledge base; it is read-only for this skill.
- Does not overwrite local `docs/` files; conflicting docs are reported for manual review.
