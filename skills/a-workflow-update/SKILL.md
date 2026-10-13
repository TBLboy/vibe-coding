---
name: a-workflow-update
description: Safely update Vibe Workflow Agents, Skills, commands, plugins, schemas, and scripts using diff, backup, apply, validation, and rollback while preserving project-specific business and execution data.
license: MIT
compatibility: codex
metadata:
  workflow: maintenance
  output: safe-update
---

# Workflow Update

## Purpose

Keep the global workflow runtime evolving without silently overwriting the user's project truth or local customizations.

## Policy

```text
inspect version → compare diff → classify files → backup → apply
→ validate syntax/schema → smoke test → report → rollback on failure
```

## File Classes

- **managed global runtime files**: global `AGENTS.md`, `agents`, `commands`, `plugins`, `skills`, `vibe-workflow/scripts`, and `vibe-workflow/project-log-template`;
- **project data**: `.project-log` business, task, decision, verification, alignment and trace records;
- **local customization**: any managed file modified by the user after installation.

Project data is create-if-missing only. Never replace it during a routine update.

## Procedure

1. Read source and target manifests.
2. Run the repository suite from its root: `"$(cat "${CODEX_HOME:-$HOME/.codex}/vibe-python")" -m unittest discover -s tests`. A green suite before the change is the cheapest rollback signal.
3. Run `python scripts/global_installer.py preflight` and review the reported interpreter, Codex version and warnings.
4. Review the change set (`git -C <repo> diff`) and any managed file the user modified locally.
5. Run `python scripts/global_installer.py update`. It writes a timestamped backup to `<codex-home>/backups/update-<stamp>/` before touching anything, and restores the previous bytes if a step fails.
6. Confirm the runtime assets and templates exist, then restart Codex to load the update. Python runtime scripts (`vibe-workflow/scripts/*.py`) take effect on their next invocation; the plugin, `AGENTS.md`, skills and commands need the restart.
7. If validation or smoke testing fails, restore the backup directory named in the install output.
8. Record material workflow changes and migration notes.

Do not implement silent unattended updates in this stage. A future remote updater must retain the same review and rollback guarantees.
