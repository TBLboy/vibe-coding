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

- **managed global runtime files**: global `AGENTS.md`, `agents`, `commands`, `plugins`, `skills`, `.vibe-workflow/scripts`, and `.vibe-workflow/project-log-template`;
- **project data**: `.project-log` business, task, decision, verification, alignment and trace records;
- **local customization**: any managed file modified by the user after installation.

Project data is create-if-missing only. Never replace it during a routine update.

## Procedure

1. Read source and target manifests.
2. Run `scripts/update_workflow.py --dry-run` against the global Codex config directory.
3. Review changed and locally modified files.
4. If safe, run with `--apply`.
5. Confirm the runtime assets and templates exist, then restart Codex to load the update.
6. If validation or smoke testing fails, restore the generated backup.
7. Record material workflow changes and migration notes.

Do not implement silent unattended updates in this stage. A future remote updater must retain the same review and rollback guarantees.
