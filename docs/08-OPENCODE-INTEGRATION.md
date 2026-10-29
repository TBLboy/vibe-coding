# OpenCode Integration Contract

## Target

Target OpenCode V2 using its documented plugin/agent APIs. This package does not claim compatibility with every V2 build. Initial isolated-plugin smoke ran on OpenCode **2.0.29**; provider-backed `/fast` and strict-review positive-path smoke later ran on the current local OpenCode **2.0.32** service. This is not a general compatibility claim for every V2 build.

Official API references checked while preparing this pack:

- Plugins and command transforms: https://dev.opencode.ai/v2/docs/build/plugins/
- Agent definitions and ordered permissions: https://dev.opencode.ai/v2/docs/agents/
- Permission semantics: https://dev.opencode.ai/v2/docs/permissions/
- Commands: https://dev.opencode.ai/v2/docs/commands/

## Plugin responsibilities

`runtime/opencode/plugins/vibe-v2/index.ts` has three narrow responsibilities:

1. Register the explicit `/fast`, `/balanced`, and `/strict` commands, persist the selected mode per OpenCode `sessionID`, and inject the authoritative mode policy into model context.
2. Keep a minimal per-Session active-Task pointer through `vibe_task_control`; the Task JSON remains the source of truth.
3. Deny `vibe-reviewer` subagent invocation unless the active Task is persisted as strict, active, in review phase, verification-passed, and a one-time review permit has been issued.

It must not watch every file operation, write project logs, run tests, maintain a second Task state machine, call external services, or install dependencies.

## Command behavior

For each command:

1. Create a one-time pending token for the explicit command.
2. Queue the mode-change prompt (`delivery: queue`) so the current action is not interrupted.
3. The queued prompt must call `vibe_set_session_mode` with the matching token before doing anything else. The tool consumes the token and stores the new mode. A fabricated, mismatched, or reused token is rejected.
4. If no trailing task text exists, the prompt confirms the mode only. If task text exists, it runs in the same queued turn after the tool succeeds.
5. Do not modify the policy of an already-started Task.

Only commands registered by the plugin change the mode. Ordinary user text and model output cannot invoke the command handler implicitly.

## Context behavior

Before each primary model request, read the mode using the current `sessionID`. If no valid value exists, use `balanced`. Inject the mode policy from `runtime/core/mode.ts`.

The policy injection must be bounded and must not include project operation history. It must clearly state that an existing Task's frozen policy takes precedence over the current Session mode for that Task. The mode-setting tool must reject calls without an unused pending token created by the explicit command handler. `vibe_task_control` verifies Task JSON before changing the per-Session pointer. The permission hook must deny reviewer calls without a matching one-time permit and must re-check the Task file before allowing the subagent.

## Agent permissions

- `vibe-main` is primary and may invoke only `vibe-reviewer` as a subagent in the baseline.
- `vibe-reviewer` is subagent-only and read-only. Its permissions must deny all actions first, then explicitly allow read-only project file access while denying known secret paths. The main Agent must provide the relevant diff/context to the reviewer; the reviewer has no shell, glob, grep, or edit permission.
- The plugin permission hook is the hard gate: a reviewer call without a valid permit for the active strict Task is denied even if the main Agent tries to invoke it in fast/balanced.
- Permission enforcement must be verified in the actual target OpenCode build. A prompt saying “do not edit” is not sufficient enforcement.

## Configuration

`runtime/opencode/opencode.json` sets `default_agent` to `vibe-main` and registers only the local V2 plugin directory at `./runtime/opencode/plugins/vibe-v2`. OpenCode 2.0.29 ignores the legacy `subagent_depth` field, so the baseline does not set it. The config intentionally does not configure model/provider, MCP, third-party plugins, or user permissions globally.

To preserve the plugin’s relative imports, stage `runtime/core/` and `runtime/opencode/` under `$OPENCODE_CONFIG_DIR/runtime/`, merge the config snippet into `$OPENCODE_CONFIG_DIR/opencode.json`, and stage the two Markdown Agents into `$OPENCODE_CONFIG_DIR/agents/`. Do not copy only the plugin file. The project templates under `skills/a-project-init/templates/` are consumed by the initialization Skill; `.vibe/sessions/` and `.vibe/tasks/` are never pre-created in a project. The installer is `scripts/vibe_v2_installer.py` (`install` / `verify` / `uninstall`). It merges `plugin` and `default_agent` into `opencode.json` while preserving the file's permission bits, keeps every other key, writes an owner-only backup that must be deleted after verification because it holds credentials, removes unmodified managed files that the current source no longer ships, and never deletes a managed file the user has edited.

## Known integration checks

Before release, verify in a clean OpenCode V2 environment:

- plugin loads without errors;
- `/fast`, `/balanced`, `/strict` appear and execute;
- bare commands change mode and only confirm;
- command plus trailing text both changes mode and executes the task;
- mode commands queue behind current work rather than interrupt it;
- a mode token is one-time, Session-scoped, and cannot be reused or used to select a different mode;
- mode survives compaction and reopening the same Session;
- a new Session defaults to balanced;
- mode storage is isolated by Session ID;
- current Task policy remains frozen after a mode change;
- main Agent can invoke reviewer in strict mode;
- reviewer cannot edit files or run arbitrary shell commands;
- reviewer is denied in fast/balanced even if the main Agent attempts to invoke it;
- reviewer is denied without a registered active Task, or when the Task is not strict / not in review / not verified;
- review permits are one-time and consumed by the permission hook;
- Task control start/resume/pause/close keeps the pointer consistent;
- missing/invalid mode storage safely defaults to balanced and does not claim a different mode.
