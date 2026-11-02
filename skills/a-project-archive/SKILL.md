---
name: a-project-archive
description: "归档/存档/备份项目记忆/保存快照 | Archive a V2 project: copy AGENTS.md and .vibe/ into a timestamped snapshot, then commit and push it so the archive survives this machine."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Project Archive

Use when the user asks to archive a V2 project, save its durable project context, or create an offline snapshot.

## Scope

Archive only these project-root inputs:

- `AGENTS.md`, when present;
- `.vibe/`, when present.

The archive is a copy-only snapshot of the source project: it does not modify the source project, infer a knowledge-base location, or archive unrelated project files. It **is** committed and pushed in the archive repository, because an archive that exists only on one machine has not been archived.

## Archive root (remembered per machine)

The destination root is stored in the installed Skill at `~/.config/opencode/skills/a-project-archive/archive_root.conf`. The installer never writes or deletes this file, so it survives framework upgrades.

The archive root should be a Git work tree with a remote. That is how snapshots get published.

1. Run the archive; it creates the snapshot and pushes it:

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py --project-root <project-root>
   ```

2. If it exits with code 3 (`No archive root is configured`), ask the user **once** for the absolute archive directory, then save it and archive in the same command:

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py \
     --set-archive-root <absolute-dir> --project-root <project-root>
   ```

   Never guess a knowledge-base location; the directory must exist and must not be inside the project.

3. The user can later change the root with `--set-archive-root`, inspect it with `--show-archive-root`, override it for one run with `--archive-root <dir>` (not saved), or name the remote with `--remote <name>`.

The command creates `<archive-root>/<project-name>/<UTC-timestamp>/` (staging first, then `manifest.json` with SHA-256 hashes, validated before publication), commits only that snapshot directory, pushes it, and confirms the remote ref equals the local commit.

## Publishing is part of archiving

Archiving finishes when the snapshot is on the remote. The script does this itself; do not stop at "archive created".

| Exit | `publish.status` | Meaning | What to do |
|---|---|---|---|
| 0 | `pushed` | Committed and pushed; remote ref confirmed | Report the commit and remote |
| 0 | `already-published` | Nothing new to publish for this snapshot | Report it; no action |
| 0 | `skipped` | `--no-push` was given | Tell the user the snapshot is local only |
| 4 | `not-a-repository` | Archive root is not a Git work tree | Tell the user; offer to init one with a remote, or re-run against a publishing archive root |
| 4 | `no-remote` | Git work tree without a remote | Ask for the remote URL, then `git remote add` and re-run |
| 1 | — | Commit/push/confirmation failed | Show the error; never claim the archive is safe |

Rules:

- **Never report an archive as done while the snapshot is unpushed.** Exit 4 means "created locally, not archived".
- Never force-push and never rewrite history. On a rejected push the script integrates once (`fetch` + `rebase`, aborting cleanly on conflict) and retries; a remaining conflict is surfaced to the user.
- Only the snapshot directory is staged and committed (`git add -- <snapshot>`), never other working-tree changes in the archive repository. Files belonging to other snapshots or unrelated edits are left alone. Publishing a branch still also publishes any earlier unpushed commits of that branch — Git cannot publish a commit without its ancestors — so keep the archive repository's history clean.
- `--no-push` exists only for a user who explicitly wants a local-only snapshot. Do not pass it on your own initiative.
- Never put credentials on a command line; rely on the user's existing Git credential helper or SSH agent.

## Safety

- Refuse a missing `.vibe/`: there is no V2 project memory to archive.
- Refuse symlinked source inputs and destination roots inside the source project.
- Preserve an existing archive; each snapshot receives a new unique directory.
- Treat the manifest as an integrity check, not as a project activity log.
- Commit and push only the new snapshot directory; never sweep in unrelated changes from the archive repository.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
