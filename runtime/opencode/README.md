# OpenCode Client Surface

This directory contains the OpenCode-native client surface for Vibe Coding. It is installed
into `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}` by the OpenCode installer.

## Surface Map

| Capability | OpenCode asset | Status |
|---|---|---|
| Global main-agent rules | `AGENTS.md` | adapted |
| Primary orchestration agent | `agents/vibe-main.md` | supported |
| Eight bounded role agents | `agents/*.md` | adapted |
| Lifecycle slash commands | `commands/vibe-*.md` | adapted |
| Reusable workflow Skills | top-level `skills/*/SKILL.md` | supported |
| Default agent and task permissions | `opencode.json` | supported |
| Session/compaction/tool hooks | `plugins/vibe-workflow.ts` | supported |
| Session Goal and automatic continuation | `@prevalentware/opencode-goal-plugin@0.1.51` | adapted |
| Install/update/uninstall | `runtime/opencode/install.sh` + `scripts/opencode_installer.py` | supported |

The Codex marketplace, Codex plugin manifest and `cc-switch` TOML generation are intentionally
not carried into this client surface. OpenCode uses its own plugin and MCP configuration.

Session Goal is delegated to `@prevalentware/opencode-goal-plugin`, pinned at `0.1.51` and
registered by the installer as a managed plugin entry. Verified on a real `opencode 1.18.31`
runtime: the client loads and registers `/goal`, `/pause_goal` and `/resume_goal`, an active goal
drives further turns by itself through `session.promptAsync`, and a closable objective reaches
`status=complete` with recorded completion evidence.

The plugin is only a session control surface. Project Goal lives in `.project-log` and is still
the only completion contract: `vibe goal` evidence gating decides completion, and the plugin's
own state never counts as evidence. Compaction survival, pause/resume semantics and the
`max_auto_turns` ceiling are not yet verified. If the plugin is absent or disabled, session
continuation falls back to explicit user instruction and must be labelled
`serial-role-fallback`.

## Installation

The OpenCode client surface is installed by `scripts/opencode_installer.py`, invoked through the
repo-local wrapper:

```bash
./runtime/opencode/install.sh install     # default when no action is given
./runtime/opencode/install.sh verify
./runtime/opencode/install.sh update
./runtime/opencode/install.sh uninstall
```

Common options:

| Option | Effect |
|---|---|
| `--opencode-home <dir>` | Target config directory instead of `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}` |
| `--skip-plugin-install` | Do not run the package manager for `@opencode-ai/plugin` |
| `--skip-preflight` | Skip tool detection; intended only for isolated package tests |

What the installer does:

- Resolves a Python 3.11+ interpreter and writes a `vibe-python` pointer next to the OpenCode config.
- Merges `AGENTS.md` as a `<!-- VIBE-OPENCODE-GLOBAL:BEGIN -->` block, so any rules the user already
  had in that file are preserved instead of overwritten.
- Copies `agents/`, `commands/`, `plugins/`, the top-level `skills/`, and the `runtime/` tree into
  the OpenCode config directory.
- Merges — never overwrites — `opencode.json`: it sets `default_agent` and registers the plugin and
  permission rules while preserving user `plugin`, `mcp`, `model`, `permission` and other keys.
  Two plugin entries are managed: `./plugins/vibe-workflow.ts` and the pinned session Goal
  controller `@prevalentware/opencode-goal-plugin@0.1.51`. The version is pinned because the global
  rule names it; each managed entry records whether the user already had it, so `uninstall` removes
  only what the installer added.
- Installs the `@opencode-ai/plugin` dependency with `npm` or `bun` unless `--skip-plugin-install`.
  `--no-audit`/`--no-fund` are npm-only and are not passed to `bun`.
- Writes install state to `<home>/.vibe-opencode-installation-state.json` and backs up any replaced
  files to `<home>/backups/<action>-<stamp>/`.

Safety properties, all covered by `tests/test_opencode_installer.py`:

- Conflicts are detected before the config is touched: a file that already exists but does not match
  the package (or that both the user and the package changed) aborts the install with a
  `pre-existing file differs from package` / `local and package versions both changed` message, and
  `opencode.json`, `AGENTS.md` and the managed assets are left byte-identical. There is no silent
  overwrite and no `--force`. A pre-run snapshot still lands in `<home>/backups/<action>-<stamp>/`
  before that check runs, so an aborted run does leave a fresh backup directory behind — that
  snapshot is what a later rollback would restore, and it never rewrites the config.
- Repeated `install`/`update` runs are idempotent: the managed plugin appears once and
  `installed_at` is stable.
- A plugin entry naming the same package at a **different version** is refused rather than
  registered alongside the managed one, so a config never ends up with two Goal controller entries.
  Unpinned entries (`@scope/name`, `@scope/name@latest`) and unrelated packages install normally.
  Ownership and conflict checks normalise surrounding whitespace and letter case, so `@Scope/Name`
  and `@scope/name` are treated as the same package.
- `verify` fails if either managed plugin entry is missing, so a config that silently lost the
  Goal controller cannot pass installation verification.
- Files the user edited after install — including `skills/**` and `vibe-workflow/**` — are reported
  as `PRESERVED local modification` and never overwritten; `uninstall` keeps them too.
- Permission rules the installer added but the user then edited are handed back to the user: `update`
  leaves the edited value alone instead of resetting it, and `uninstall` keeps it.
- Permission rules the user deletes are not silently restored; `update` reports
  `managed rule removed by the user` and leaves the deletion in place.
- `uninstall` only removes managed files whose hash still matches the installed version, then
  removes only what the installer added: the plugin registration, `default_agent`, managed
  permission rules and the `package.json` dependency. Values that already existed before install
  are restored to their previous content rather than deleted.
- If the installer created `opencode.json` and every key in it was installer-owned, `uninstall`
  removes the file instead of leaving a `$schema`-only stub.
- `$schema` follows the same ownership rule as permissions: a value the user edited or deleted
  after install is handed back to the user and is not overwritten or removed.
- Install, update and uninstall are transactional over the files they touch. If any step fails —
  including the package manager — the previous bytes of `opencode.json`, `AGENTS.md`, the assets,
  the runtime, `package.json`, `vibe-python` and the state file are restored, and any `node_modules/`,
  `package-lock.json` or directory that the failed run created is removed, so it never leaves a
  half-installed tree.
- Lockfiles (`package-lock.json`, `bun.lock`, `bun.lockb`, `yarn.lock`, `pnpm-lock.yaml`) are
  snapshotted before a run and restored on rollback, including when they already existed. A
  pre-existing `node_modules/` is never deleted, but the package manager may still have rewritten it
  before a failure; the lockfile is restored so the next install can reconcile it.
- `uninstall` validates `opencode.json`, `package.json` and the `AGENTS.md` block before deleting
  anything. A damaged or unparsable file aborts the run with nothing removed.
- `AGENTS.md` block removal is conservative: if the BEGIN/END markers are missing, duplicated or out
  of order, the installer refuses to edit the file rather than truncating user content.
- Uninstall prunes only the exact directories the installer created (recorded at install time,
  deepest first) and only when they are empty; a directory the user filled is left in place.
- Every path taken from installation state (`managed_files`, `created_dirs`) is validated as a
  relative path that stays inside the OpenCode home. Absolute paths and `..` segments are rejected
  with `unsafe installation path in installation state`, so a corrupted state file cannot delete
  files outside the config directory.
- Every installer-touched path is resolved before use — managed assets, `AGENTS.md`,
  `opencode.json`, `package.json`, `vibe-python`, the state file, lockfiles, the backup directory and
  rollback targets. If a symlink planted inside the config directory points outside it, the installer
  refuses with `refusing to touch a path outside the OpenCode home` instead of writing or deleting
  through the link. Symlinking these files elsewhere is therefore unsupported.
- `node_modules/` is boundary-checked before the package manager runs, so a `node_modules` symlink
  pointing outside the home aborts the install before anything is written. Symlinks *inside*
  `node_modules` that npm or bun creates are owned by the package manager and are not audited.
- The boundary check is not a sandbox. It closes the static symlink-escape paths; a concurrent
  attacker who swaps a parent directory between the check and the write (TOCTOU) is out of scope for
  this single-user installer.
- `node_modules/` and `package-lock.json` are left to the package manager on uninstall; the
  installer restores `package.json` but does not delete shared dependency trees.
- No action ever touches a `.project-log/` directory, including one located inside the OpenCode home.

`opencode debug config --pure` only resolves config and does not import external plugins; it is not a
substitute for `verify` or for a real OpenCode run. A clean-room dependency install and a real
model-driven run are validated by TASK-073 / TASK-075.

Known limitations of the installer:

- `preflight` records whether the `opencode` CLI is on `PATH` but does not require it. Installing the
  config surface and runtime without the CLI is intentional, so the assets can be staged first.
- It reads and writes `opencode.json` as strict JSON. A config that only exists as `opencode.jsonc`,
  or that contains comments, is not merged; the installer creates a separate `opencode.json`. Move
  user settings into `opencode.json` first if you rely on JSONC.
- It refuses to guess. If `opencode.json` is not valid JSON, the install stops before writing and
  reports the parse error instead of rewriting the file.

## Agent Roles

`vibe-main` is the only primary agent. It owns user interaction, C-level decisions, project-log
consistency, cross-role integration and final completion judgment.

The following subagents are available through the OpenCode `task` tool:

- `business-analyst`
- `codebase-onboarder`
- `solution-researcher`
- `implementation-builder`
- `verification-reviewer`
- `alignment-reviewer`
- `paper-reader`
- `workflow-distiller`

Read-only roles explicitly deny the `edit` tool. `verification-reviewer` and `alignment-reviewer`
additionally deny Bash by default and allow only read-only `git`/search commands plus the unittest
and package-validation entry points; any other shell command is denied even under `--auto`.
Those entry points go through `bin/vibe-python`, a machine-independent wrapper that execs the
interpreter named in the `vibe-python` pointer next to the config. The wrapper exists because
OpenCode expands only `~` and `$HOME` in permission patterns and never `$VIBE_PYTHON`, while the
real interpreter path can sit outside the home directory. The allowlist names the wrapper with its
two exact subcommands (`-m unittest*` and `runtime/scripts/validate_package.py*`) rather than the
bare wrapper, so a read-only role cannot reach `vibe-python -c "<arbitrary python>"`. `sha256sum`
is allowed so a reviewer can recompute artifact hashes instead of trusting the implementer's. The
allowlist is pinned to the default `~/.config/opencode` location: with a custom
`OPENCODE_CONFIG_DIR` the wrapper patterns do not match, and independent review then fails
explicitly instead of silently falling back to a possibly older `python3` on `PATH`.
Research, onboarding, paper-reading, `business-analyst` and `workflow-distiller` roles have Bash
fully denied and rely on built-in read/search tools or web tools. `business-analyst` and
`workflow-distiller` may write draft records under `.project-log/**`; they cannot edit product
code. Subagents cannot invoke other subagents.

These settings are OpenCode permission policies, not an OS sandbox. The test allowlist still
executes project test code with the reviewer's user privileges.

## Commands

| Command | Purpose |
|---|---|
| `/vibe-start` | Initialize or start a Vibe Coding project |
| `/vibe-resume` | Restore state and continue the current task |
| `/vibe-plan` | Clarify, research, baseline and decompose work |
| `/vibe-implement` | Specify and implement an approved task |
| `/vibe-verify` | Verify acceptance criteria and record evidence |
| `/vibe-status` | Show the authoritative current state |
| `/vibe-retro` | Run retrospective and evidence-backed distillation |

Natural-language triggers remain valid; commands are thin entry points, not a second workflow.

## Plugin Hooks

`plugins/vibe-workflow.ts` is registered by `opencode.json` and never advances a task, completes a
Goal, rewrites business logic, or edits Skills:

| Hook | Behavior |
|---|---|
| `experimental.chat.system.transform` | Inject a bounded `vibe status` snapshot |
| `experimental.session.compacting` | Refresh generated views, then inject state and preservation rules |
| `tool.execute.after` | Debounce a `vibe evidence refresh` after file-writing tools |
| `vibe_workflow_status` | Read-only tool exposing `vibe status` / `vibe context <task>` |

Its runtime is resolved from `VIBE_RUNTIME_SCRIPT`, `VIBE_RUNTIME`, the OpenCode config directory,
or a development fallback; when none is available the hooks degrade to an explicit "no runtime"
message. Its only writes are `vibe evidence refresh` and the generated local views produced by
`vibe state-views`; neither changes task, Goal, or business facts.
Installing these assets and their `@opencode-ai/plugin` dependency is `TASK-073`.

The unit tests import the plugin directly and exercise every hook; live OpenCode import/registration
was verified once with a real non-`--pure` OpenCode run. `opencode debug config --pure` only resolves
the config and does not import external plugins. A real model-driven session, compaction, and write
tool loop still belongs to TASK-075.
