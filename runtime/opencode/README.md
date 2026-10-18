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
| Session/compaction/tool hooks | `plugins/vibe-workflow/index.ts` (V2 directory plugin) | supported |
| Session Goal and automatic continuation | `@prevalentware/opencode-goal-plugin@0.1.60` | adapted |
| Install/update/uninstall | `runtime/opencode/install.sh` + `scripts/opencode_installer.py` | supported |

The codex delivery face (its marketplace, plugin manifest, CLI hooks, role templates and
`cc-switch` TOML generation) is no longer carried in this repository at all -- it lives on the
`codex` branch. OpenCode uses its own plugin and MCP configuration.

Only OpenCode **V2** is supported (verified on `opencode 2.0.27`). V2 changed the plugin API: a
plugin is a directory whose default export is `{ id, setup }`, and V1 function exports or
single-file plugin paths are rejected. The V1 plugin `plugins/vibe-workflow.ts` is therefore gone;
`update` removes it and its `./plugins/vibe-workflow.ts` registration.

Session Goal is delegated to `@prevalentware/opencode-goal-plugin`, pinned at `0.1.60` and
registered by the installer as a managed plugin entry. `0.1.60` is the first release that loads on
V2 (`0.1.51` fails with `Schema.optionalWith is not a function` against the Effect v4 that V2
injects); an installer-owned `0.1.51` entry is migrated on `update`. On `opencode 2.0.27` the
plugin loads with status `active` and registers `/goal`, `/pause_goal` and `/resume_goal`.

The plugin is only a session control surface. Project Goal lives in `.project-log` and is still
the only completion contract: `vibe goal` evidence gating decides completion, and the plugin's
own state never counts as evidence. Compaction survival and pause/resume semantics are not yet
verified.

The plugin's built-in ceilings are real on an installer-managed spec: `max_auto_turns` (`25`),
`max_no_progress_turns` (`2`) and `max_prompt_failures` (`3`) default to values that stop a long
run, and `0` is not a way out -- the plugin parses them with `positiveIntegerOrNull`, so `0` falls
back to the default. They are configurable through the options tuple
(`["@prevalentware/opencode-goal-plugin@0.1.60", { ... }]`); option delivery was verified on
`opencode 2.0.27` (setting `register_command: false` removes `/goal` from `/api/command` after
`opencode reload`). Because the installer only recognises string specs, such an entry must then be
handed back with `--without-plugin goal`, or `verify` fails and a second spec gets appended.
`AI_INSTALL.md` carries the procedure.

If the plugin is absent or disabled, session continuation falls back to explicit user instruction
and must be labelled `serial-role-fallback`.

## Concurrent Project Log Runs

Project Log format 2 permits independent Runs to be active together only when their declared product
write scopes are disjoint. `vibe task begin` requires immutable `--owner`, `--session-id`, and one or
more literal project-relative `--write-scope` roots. Equal, parent/child, or workspace-wide (`.`)
scopes conflict; `status` exposes `active_runs`/`active_tasks` rather than silently choosing a current
Run. The SQLite write transaction, ledger-first append and revision/generation CAS remain global and
atomic; the Run scope governs product-write coordination, not those Project Log maintenance writes.

Owner/session fields are audit attribution only: the CLI envelope has no trustworthy caller identity,
so they are not authorization. Schema-4 Runs migrate without ledger rewrites as
`legacy`/`legacy`/`["."]`; a still-active legacy Run deliberately remains workspace-wide until its
existing lifecycle closes it. See `docs/USAGE.md` for the exact scope grammar and command examples.

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
| `--with-plugin NAME` / `--without-plugin NAME` | Enable/disable an optional plugin (repeatable; names come from `optional-integrations.json`) |
| `--with-mcp NAME` / `--without-mcp NAME` | Enable/disable an optional MCP server (repeatable) |
| `--list-integrations` | Print the integration catalog, its defaults and the current selection; writes nothing |
| `--skip-preflight` | Skip tool detection; intended only for isolated package tests |

What the installer does:

- Resolves a Python 3.11+ interpreter and writes a `vibe-python` pointer next to the OpenCode config.
- Merges `AGENTS.md` as a `<!-- VIBE-OPENCODE-GLOBAL:BEGIN -->` block, so any rules the user already
  had in that file are preserved instead of overwritten.
- Copies `agents/`, `commands/`, `plugins/`, the top-level `skills/`, and the `runtime/` tree into
  the OpenCode config directory.
- Merges — never overwrites — `opencode.json`: the shipped file is two lines
  (`$schema`, `default_agent`) and the installer merges the selected integrations into the
  user's `plugin`/`plugins` and `mcp` keys, preserving `model`, `permission` and anything
  else. What gets installed comes from `runtime/opencode/optional-integrations.json` plus
  the selection recorded in the installation state, so an empty install ships no
  third-party entry at all. A plugin entry with `pinned_spec` keeps that exact version --
  the Goal controller is pinned because the global rule names one version; the others are
  registered by bare package name and OpenCode resolves them. Every managed entry records
  whether the user already had it, and a user edit or deletion is respected, so
  `uninstall` removes only what the installer added and never resurrects a user choice.
- Does **not** list `plugins/vibe-workflow/` in `opencode.json`: V2 discovers plugin directories
  under the config `plugins/` folder by itself, and listing it as well loads it twice.
- Installs no npm dependency. V2 provides the plugin API (`@opencode/plugin`) itself; `update`
  removes the `@opencode-ai/plugin` entry an older release added to `package.json`.
- `preflight` reports the OpenCode version and stops on a 1.x CLI. When `opencode` is not on PATH it
  looks for the desktop application's bundled CLI (`/opt/OpenCode/resources/opencode-cli`) and
  prints the symlink command; a set `PYTHONPATH` is reported as a warning.
- Writes install state to `<home>/.vibe-opencode-installation-state.json` and backs up any replaced
  files to `<home>/backups/<action>-<stamp>/`.

Safety properties, all covered by `tests/test_opencode_installer.py`:

- File conflicts are detected before anything is written: a file that already exists but does not
  match the package (or that both the user and the package changed) aborts the install with a
  `pre-existing file differs from package` / `local and package versions both changed` message, and
  `opencode.json`, `AGENTS.md` and the managed assets are left byte-identical — no backup directory
  is created on this path. There is no silent overwrite and no `--force`.
- Repeated `install`/`update` runs are idempotent: the managed plugin appears once and
  `installed_at` is stable.
- A plugin entry naming the same package at a **different version** is refused rather than
  registered alongside the managed one, so a config never ends up with two Goal controller entries.
  This check runs inside the config merge, after the pre-run snapshot, so a refused version conflict
  does leave a fresh directory in `<home>/backups/<action>-<stamp>/` — that snapshot is what a later
  rollback would restore, and the config itself is never rewritten. Unpinned entries (`@scope/name`,
  `@scope/name@latest`) and unrelated packages install normally. Ownership and conflict checks
  normalise surrounding whitespace and letter case, so `@Scope/Name` and `@scope/name` are treated
  as the same package.
- `verify` fails if the Goal controller entry is missing, if the V1 `./plugins/vibe-workflow.ts`
  registration or file is still present, or if `plugins/vibe-workflow/index.ts` is missing.
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
additionally deny Bash by default and allow only read-only `git`/search commands plus the trusted
verification runner; any other shell command is denied even under `--auto`. The runner is reached
through its own path and subcommand (`*verification_runner.py preflight*` and
`*verification_runner.py run*`) rather than through a wrapper: OpenCode expands only `~` and
`$HOME` in permission patterns, and the installed `bin/vibe-python` is a POSIX shell script, so
pinning the allowlist to it left a Windows reviewer unable to run anything at all. The runner
enforces the interpreter floor itself (`python>=3.11`) and answers an older interpreter with
`verification_capability_missing`, so allowing any interpreter cannot silently downgrade a review.
Digests are re-derived with the runner's `hash` action (`run --action hash --paths <file>`), which
is why the allowlist carries no `sha256sum`: a permission entry for a command that does not exist
on this platform advertises a capability the reviewer cannot actually use. Independent review
fails explicitly rather than silently falling back to a possibly older `python3` on `PATH`.
Read-only `git` inspection is allowlisted as a small set of exact forms (`git status`, `git diff`,
`git log`, `git show`, `git rev-parse`, `git ls-files`). Explicit `git log --format=` /
`git log --pretty=` entries were added, then removed on 2026-10-15: the plain `git log*` already
matches `git log --format=%H -1`, so they were redundant insurance rather than a fix, and a literal
copy of the pattern list proves nothing about whether a command is actually permitted. The test now
pins the resolved effect of a real command instead. A command the matcher denies is a capability gap
to report, never a reason to widen the allowlist.
Research, onboarding, paper-reading, `business-analyst` and `workflow-distiller` roles carry no
general Bash access: they rely on the built-in read/search tools or web tools. They may run directory
inspection only — `ls`, `pwd`, `wc`, `stat` — which is content-blind (none of these can print a file's
bytes) and, unlike `find` or `git diff --no-index`, has no flag that writes or executes. `find` is
deliberately absent because it ships `-exec`/`-delete`/`-fprint`; anything that can print contents
(`cat`, `head`, an interpreter) stays denied, since a shell allow would otherwise bypass the secret
`read` denies entirely. `business-analyst` and `workflow-distiller` may write draft records under
`.project-log/**`; they cannot edit product code. Subagents cannot invoke other subagents.

Measured on 2026-10-15 for that listing allowlist: `ls`, `pwd`, `ls -R`, `wc -l` and `stat` all run,
while `cat`, `head`, `find`, `find -exec cat`, an interpreter and `rm -rf` are all denied, and **no
listed verb printed a file's bytes**. Note the asymmetry the same probe exposed: the shell action
matches the command *string*, not a parsed path, so `ls /etc` succeeded — the shell allowlist is
verb-based and carries **no** outside-the-workspace gate, unlike the file tools, which do honour
`external_directory`. A listing verb therefore discloses filenames outside the Location (no contents).
Keep this set content-blind: one verb that can print bytes would step around the secret `read` denies
that the file tools still enforce.

These settings are OpenCode permission policies, not an OS sandbox. The test allowlist still
executes project test code with the reviewer's user privileges.

A path outside the Location is a hard deny for every read-only role. That is deliberate, not an
oversight: `ask` is not a usable middle ground here. Measured on 2026-10-15 (OpenCode desktop 2.0.29),
relaxing a role's rule to `external_directory: ask` made a `read` of `/etc/hosts` succeed silently
with no prompt at all, where the same call had been a hard `Permission denied: external_directory`
before the change. An `ask` that no client ever surfaces is a privilege grant, not a gate, so a role
that must not reach a path keeps `deny` plus explicit directory allows. Outside the Location the
runtime answers `Permission denied: external_directory`. Configuration changes of this kind take
effect on `opencode reload`.

Two further measured properties constrain how such a boundary may be drawn:

- **Only the `<dir>/*` shape works.** A literal file entry (`~/.config/opencode/AGENTS.md`) and a
  non-boundary wildcard (`~/.config/opencode/*.md`) both stayed denied, while `~/.config/opencode/*`
  was honoured (measured 2026-10-15). The global `AGENTS.md` sits at the config root, so opening it for
  one role would also admit `opencode.json` — which is why the boundary is drawn at subdirectories.
- **The boundary is the only thing protecting the secrets inside it.** `grep`'s permission resource is
  its search *pattern*, not its search path, so the `read` deny does not constrain it. Measured
  2026-10-15 with `external_directory: ~/.config/opencode/*` in place: `read` on `opencode.json` was
  denied (`Permission denied: read`), while `grep` pointed at that same file returned its content.
  Keep the secrets outside every allow-listed boundary; never widen one to cover the config root.

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

`plugins/vibe-workflow/index.ts` is a V2 directory plugin (`Plugin.define({ id, setup })`),
auto-discovered from the config `plugins/` folder. It never advances a task, completes a Goal,
rewrites business logic, or edits Skills:

| V2 hook | Behavior |
|---|---|
| `ctx.session.hook("context")` | Inject a bounded `vibe status` snapshot |
| `ctx.session.hook("compaction")` | Refresh generated views, then inject state and preservation rules |
| `ctx.tool.hook("execute.after")` | Debounce a `vibe evidence refresh` after file-writing tools |
| `ctx.tool.transform` → `vibe_workflow_status` | Read-only tool exposing `vibe status` / `vibe context <task>` |

The project root is resolved on every call — the session's directory (`ctx.session.get`), then the
plugin instance location — so a `.project-log/` created after the plugin loaded is picked up
without a restart. The runtime script is resolved from `VIBE_RUNTIME_SCRIPT`, `VIBE_RUNTIME` or the
OpenCode config directory; when none is available the hooks degrade to an explicit "no runtime"
message. Runtime calls drop `PYTHONPATH` so a foreign Python install cannot shadow the runtime's
dependencies. Its only writes are `vibe evidence refresh` and the generated local views produced by
`vibe state-views`; neither changes task, Goal, or business facts.

`tests/test_opencode_plugin.py` drives every hook through a stub V2 context, and
`tests/test_opencode_surface.py` starts an isolated `opencode serve` (when a V2 CLI is available) and
checks that both plugins load with status `active`. A real model-driven session, compaction, and
write tool loop is outside the automated tests.
