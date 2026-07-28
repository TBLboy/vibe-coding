---
name: a-project-log-archive
description: Archive the current project's .project-log to the centralized knowledge base for later analysis. Use when the user wants to save progress, archive records, or sync project logs.
license: MIT
compatibility: codex
metadata:
  type: tool-skill-pack
  output: synced-and-pushed-project-log
---

# Project Log Archive

Archive the current project's `.project-log/` into the knowledge base and push the knowledge base to remote.

## When to Use

The user asks to archive project logs, save progress, sync records, or "归档".

## First Run — Path Setup

Before the first archive, the knowledge base path must be configured. The script checks a config file at `<skill-dir>/scripts/kb_path.conf`. If the file is missing or contains the placeholder `__UNSET__`, the script will report the missing config. In that case:

1. Ask the user for the absolute path to their `My_knowledge_base` on this machine.
2. Verify the path exists, is a directory, and contains `工程记录/`.
3. Write the verified path to the config file.

Only the `工程记录/` subdirectory within the knowledge base will be affected by archiving.

## What It Does

1. Load the KB path from config.
2. Determine the project name from `--project-root`.
3. Verify `.project-log/` exists in the project root.
4. Find or create `<project-name>/` under `<kb>/工程记录/`.
5. Delete old `.project-log/` if present, then copy the current one.
6. Run `git add -A && git commit -m "archive: <project-name>" && git push` in the knowledge base.

## Execution

```bash
python3 ~/.codex/skills/a-project-log-archive/scripts/archive.py \
  --project-root <project-root-path>
```

## Safety

- Only copies directories containing `.project-log/`.
- Reports conflict if project name collides with an unrelated directory.
- Only affects `<kb>/工程记录/`, never other files.
