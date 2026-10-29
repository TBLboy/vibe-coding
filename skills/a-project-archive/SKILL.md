---
name: a-project-archive
description: "Project archive."
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

The archive is a copy-only timestamped snapshot. It does not modify the source project, infer a knowledge-base location, commit to Git, push, or archive unrelated project files.

## Archive root (remembered per machine)

The destination root is stored in the installed Skill at `~/.config/opencode/skills/a-project-archive/archive_root.conf`. The installer never writes or deletes this file, so it survives framework upgrades.

1. Run the archive directly; it uses the remembered root:

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py --project-root <project-root>
   ```

2. If it exits with code 3 (`No archive root is configured`), ask the user **once** for the absolute archive directory, then save it and archive in the same command:

   ```bash
   python3 ~/.config/opencode/skills/a-project-archive/scripts/archive_v2.py \
     --set-archive-root <absolute-dir> --project-root <project-root>
   ```

   Never guess a knowledge-base location; the directory must exist and be outside the project.

3. The user can later change it with `--set-archive-root`, inspect it with `--show-archive-root`, or override it for one run with `--archive-root <dir>` (not saved).

The command creates `<archive-root>/<project-name>/<UTC-timestamp>/`, stages the copy first, writes `manifest.json` with SHA-256 hashes, validates the published snapshot, and prints its path.

## Safety

- Refuse a missing `.vibe/`: there is no V2 project memory to archive.
- Refuse symlinked source inputs and destination roots inside the source project.
- Preserve an existing archive; each snapshot receives a new unique directory.
- Treat the manifest as an integrity check, not as a project activity log.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
