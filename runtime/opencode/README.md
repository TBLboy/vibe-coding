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
| Goal and automatic continuation | `TASK-072` plugin integration | deferred to Goal task |
| Install/update/uninstall | `TASK-073` installer | deferred to installer task |

The Codex marketplace, Codex plugin manifest and `cc-switch` TOML generation are intentionally
not carried into this client surface. OpenCode uses its own plugin and MCP configuration.

This surface has no session Goal and no `/goal` command. Project Goal lives in `.project-log` and
is the only completion contract; session continuation is explicit until TASK-072 ships a verified
runner interface.

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
