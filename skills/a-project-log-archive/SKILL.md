---
name: a-project-log-archive
description: Archive the current project's .project-log to the centralized knowledge base for later analysis. Use when the user wants to save progress, archive records, or sync project logs.
license: MIT
compatibility: opencode
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
2. Determine the project name from `--project-root` (the work folder name).
3. Verify `.project-log/` exists in the project root.
4. Verify the KB copy of `.project-log/state-format.json` has the same `project_id`.
5. Verify the KB ledger is an exact prefix of the local ledger, so only new commands are added.
6. Merge the local `.project-log/` into `<kb>/工程记录/<project-name>/.project-log/`,
   excluding `.state/`, `.git`, `.migration/`, `legacy/new-writes/` and copying the ledger separately.
7. Stage only `工程记录/<project-name>`, verify the staged ledger is byte-identical to the
   local ledger, then `git commit --only -- 工程记录/<project-name>`, re-verify the
   committed blob, and push `HEAD` to the checked-out branch's upstream ref with an
   explicit refspec.
8. Fail loudly instead of reporting `no-changes` whenever either blob differs from the
   local ledger: an ignored, `skip-worktree`, or `assume-unchanged` ledger keeps the index
   stale while unrelated files still stage, and a content filter or end-of-line
   conversion rewrites the ledger on the way into Git. Both would otherwise be reported
   as a successful archive.
9. Fail unless **every** push URL of that remote reports the archived revision after the
   push, so a remote hook that rewrites or rejects the ref cannot be mistaken for a
   successful archive.

Re-running the archive is idempotent: unchanged logs produce no commit.

## Execution

```bash
python3 "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/a-project-log-archive/scripts/archive.py" \
  --project-root <project-root-path>
```

## Safety

- Only copies directories containing `.project-log/`.
- Refuses when the KB holds commands the local ledger is missing; run the
  align-project-progress skill first so the two histories are merged.
- Refuses when the KB `project_id` differs from the local one, so two unrelated
  projects that share a folder name can never overwrite each other.
- Refuses when the KB `.gitignore` excludes the archived ledger, and prints the matching
  rule plus the negation lines to add, so a globally ignored `.project-log/` can never
  turn into a silent no-op.
- Refuses to commit or push unless the ledger blob in the knowledge base index and in the
  new commit is byte-identical to the local ledger, so an ignored, skipped, filtered, or
  otherwise rewritten ledger can never be reported as archived.
- Rejects content filters and end-of-line conversion on the ledger path by design: the
  ledger must reach the remote as the exact bytes that were written locally.
- Pushes to the upstream of the checked-out branch only, with an explicit refspec, so
  `remote.<name>.push` or `push.default` can never redirect the archive to another ref.
  Detached HEAD and branches without an upstream are refused before anything is committed.
- Refuses a push target that resolves back to the knowledge base itself, because pushing
  and verifying against the same repository would prove nothing. `file://` URLs carrying
  a host component (`file://localhost./…`, `file://127.0.0.1/…`, `file://random.invalid/…`,
  `file://localhost:123/…`, `file://%6cocalhost/…`) are refused outright: Git still opens a
  local path for them, but the rendering is platform-dependent, so they are treated as
  unverifiable rather than as a remote. Plain paths, `file:///absolute/path` and
  `file://localhost/absolute/path` remain supported.
- Expands a leading `~` before that comparison, because `git push ~/kb` reads `$HOME/kb`.
  A `~` that cannot be expanded (`~user` with no such account) is refused rather than read
  as a relative directory name.
- Resolves the publish target **before** copying anything into the knowledge base, so a
  rejected upstream, detached HEAD, or self-referential remote leaves the KB worktree clean.
- Verifies every configured push URL after pushing and reports failure when any of them
  does not hold the archived revision.
- Pushes the whole fast-forward range of the archive branch, exactly like a normal
  `git push`. Only the archive commit itself is path-limited to `工程记录/<project-name>`,
  so keep unrelated local work off the branch that receives the archive.
- Re-attempts a push an earlier run left behind: when nothing new needs committing but the
  upstream ref does not hold the current revision, the archive pushes instead of reporting
  `no-changes`.
- Never copies the local SQLite cache (`.state/`) or Git internals.
- Merges instead of replacing, so an existing KB copy is never deleted wholesale.
- Commits with an explicit pathspec, so `<kb>/工程记录/` is the only thing the archive
  commit can publish; other files already staged in the knowledge base stay staged.
