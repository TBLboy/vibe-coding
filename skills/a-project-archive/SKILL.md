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

## Archive repository and layout

Two settings are remembered per machine in `~/.config/opencode/skills/a-project-archive/archive_root.conf`
(JSON: `{"repository": "…", "snapshot_dir": "…"}`). The installer never writes or deletes this file, so it
survives framework upgrades.

- `repository` — the Git work tree that receives archive commits; publishing requires a remote;
- `snapshot_dir` — the directory *inside* that repository that holds project snapshots
  (`工程记录` on this machine; `.` only for a repository used exclusively for archives).

Effective snapshot parent: `<repository>/<snapshot_dir>`; a run creates
`<repository>/<snapshot_dir>/<project-name>/<UTC-timestamp>/`.

### This machine

| Setting | Value |
|---|---|
| repository | `D:\Project\My_knowledge_base` (remote `TBLboy/My_knowledge_base`, branch `work_record`) |
| snapshot_dir | `工程记录` |
| snapshot path | `D:\Project\My_knowledge_base\工程记录\<project-name>\<UTC-timestamp>\` |

Repository layout — **archives belong in `工程记录/` only**:

```text
My_knowledge_base/
  AGENTS.md
  .gitignore
  个人简历/  学习记录/  学习路线/  工作记录/      # personal files: never write here
  工程记录/                                     # the only archive entry point
    README.md
    <project-name>/                             # one directory per project
      AGENTS.md                                 # legacy V1 archive file (leave as is)
      .project-log/                             # legacy V1 memory snapshot (read-only)
      <UTC-timestamp>/                          # V2 snapshot produced by this Skill
        AGENTS.md
        .vibe/
        manifest.json
    boss_electrics/  cucumber/  data_collect/  …  Transformer-Koopman/  vibe-coding/  …
```

Layout rules:

- A snapshot is always `<repository>/<snapshot_dir>/<project>/<timestamp>/`. Never at the repository
  root, never inside another project's directory.
- Never modify or delete existing snapshots, other projects, or the unrelated top-level directories.
- `工程记录/<project>/.project-log/` is a pre-timestamp V1 snapshot. Keep it; do not migrate or rewrite it.
- Only the new snapshot path is staged and committed, so unrelated working-tree changes in the archive
  repository are never swept in.
- Self-check after a run: the reported path must contain `工程记录`. If it does not, the snapshot landed
  in the wrong place — delete it and re-run with the location set correctly.

### Commands

1. Configure once (already done on this machine):

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py \
     --set-archive-root "D:/Project/My_knowledge_base/工程记录"
   ```

   Naming the snapshot directory is enough: the script canonicalises it to
   `repository=D:/Project/My_knowledge_base`, `snapshot_dir=工程记录`. Passing the repository root instead
   implies `snapshot_dir=.`, which is only correct for a repository dedicated to archives.

2. Archive; it creates the snapshot and pushes it:

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py --project-root <project-root>
   ```

3. If it exits with code 3 (`No archive root is configured`), ask the user **once** for the archive repository
   (or the snapshot directory inside it), then save and archive in the same command:

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py \
     --set-archive-root <absolute-path> --project-root <project-root>
   ```

   Never guess a knowledge-base location; the directory must exist and must not be inside the project.

4. Inspection and overrides: `--show-archive-root` prints `repository`, `snapshot_dir` and the resolved
   `snapshot_parent`; `--set-snapshot-dir <rel>` changes only the snapshot directory; `--archive-root <dir>`
   and `--snapshot-dir <rel>` override for one run without saving; `--remote <name>` selects the remote.

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
- Never place a snapshot at the root of a knowledge-base repository that has a dedicated snapshot directory.
- Treat the manifest as an integrity check, not as a project activity log.
- Commit and push only the new snapshot directory; never sweep in unrelated changes from the archive repository.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
