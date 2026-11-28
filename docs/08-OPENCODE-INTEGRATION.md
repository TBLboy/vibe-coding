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

1. Register the explicit `/fast`, `/balanced`, and `/strict` commands, persist the selected mode per OpenCode `sessionID`, and inject the authoritative mode policy into model context. Successful switch feedback reports a different registered frozen policy when present, without modifying or resuming the Task; a bare command is acknowledgement-only.
2. Own registered Task transitions through `vibe_task_control`, with a per-Session pointer and project-scoped integrity receipt; Task JSON remains canonical.
3. Deny reviewer admission without a current one-time permit, and accept verdicts only from the correlated native completion or the bound background child's host-owned successful terminal result. Admission and background launch are not completion (canonical protocol: `03-STATE-MACHINE.md`). Expose one bounded read-only reviewer locator using that existing authorization; no new persisted state.

This core adapter must not watch every file operation, write project logs, run tests, maintain a second Task state machine, call external services, or install dependencies.

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

The policy injection must be bounded and must not include project operation history. It must clearly state that an existing Task's frozen policy takes precedence over the current Session mode for that Task. The mode-setting tool must reject calls without an unused pending token created by the explicit command handler. `vibe_task_control` validates and writes Task JSON through the state machine; direct edits invalidate the receipt. The permission hook must deny reviewer calls without a matching one-time permit and must re-check the Task file before allowing the subagent.

The injected text is a compact policy/fact reference, not the full Agent or Memory contract. New-work policy and any differing frozen Task policy are explicitly scoped. An inactive pointer is not a resume instruction. Keep root, exact recovery path and Task identity intact; do not truncate paths, read project memory into the system prompt, or remove the child-reviewer exception. Workbench status injection is unchanged. Managed Skills share the compact `V2 operating rules` footer; domain-specific safeguards remain in their own bodies. The main Agent and `06-AGENT-CONTRACT.md` own context acquisition and evidence handling.

### Native compaction and cache boundary

Use the host's native compaction, not a second summary service, snapshot type, context interceptor or token mode. [OpenCode V2 Compaction](https://dev.opencode.ai/v2/docs/compaction/) documents lossy summaries, recent-context retention (`compaction.keep.tokens`), reserved window (`compaction.buffer`), automatic/background settings and manual requests. V1 pruning/tail-turn settings are not the V2 contract. Check the exact target build and actual model window before any user-approved tuning; this package sets no compaction/model/provider configuration and assumes no fixed token limit. Background summaries can incur cost even if never used. After compaction or reopening, recover authoritative Session/Task facts from the next context injection, and recover only needed work/knowledge using `05-MEMORY-CONTRACT.md`. Do not trigger compaction routinely or use it to bypass strict review. A compacted reviewer child is not an accepted verdict under `03-STATE-MACHINE.md`.

[OpenCode Skills](https://dev.opencode.ai/v2/docs/skills/) supports discovery followed by native loading on demand. [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) motivates targeted retrieval and high-signal tool results. [OpenAI prompt caching](https://platform.openai.com/docs/guides/prompt-caching) illustrates provider-specific cached-input accounting: stable instructions may benefit from caching, but cache hits are not eliminated context occupancy. No cache implementation or guaranteed savings is implied. Measure full task usage, not only one prompt length, and separate input, output, cached input, compaction and reviewer overhead where the host exposes them.

## Agent permissions

- `vibe-main` is primary and may invoke only `vibe-reviewer` as a subagent in the baseline.
- `vibe-reviewer` is subagent-only and read-only. Its permissions deny all actions first, explicitly allow native read and `vibe_review_search`, and deny known secret paths. The main Agent still supplies complete diff and verification evidence; the reviewer independently locates relevant paths/lines and inspects current files. Native shell, glob, grep, skill, web, external-directory and edit stay denied. For an identified Reviewer, the permission hook also denies every action except read and the locator, plus known protected read paths, even if later Session rules grant them. Host identity/permission enforcement remains a live acceptance gate.
- The plugin permission hook is the hard gate: a reviewer call without a valid permit for the active strict Task is denied even if the main Agent tries to invoke it in fast/balanced.
- Permission enforcement must be verified in the actual target OpenCode build. A prompt saying “do not edit” is not sufficient enforcement.
- [OpenCode permissions](https://dev.opencode.ai/v2/docs/permissions/) documents grep matching the expression rather than the target path and shell inheriting host authority. Instead of broadening these grants, `vibe_review_search` uses bounded Node filesystem traversal and an existing verification path inventory. No subprocess, network or file write in the locator. Its execution gate reuses the consumed permit, receipt and host child identity/workspace; a child can start before launch binding, while the bound child is checked once available. Terminal or unauthorized children are refused. The host [plugin permissions API](https://dev.opencode.ai/v2/docs/build/plugins/server/) is required; the tool asserts its own action and read permissions before text access and before path results are returned, fails closed when unavailable or denied. Paths are workspace-relative; search results do not include contents. Native read remains host-enforced, not a new sandbox. Known sensitive names, linked/nonregular files and generated directories are excluded by the locator; oversized/binary files are excluded from text search. Inventory names are snapshot references, not live filesystem evidence. Per call, cap traversal at 10,000 entries, text candidates at 1,000 files / 24 MiB total / 512 KiB per file, and matches at 100; narrow scope/query after partial results. A host read denial aborts the call, even if a denied text candidate would have had no match. It cannot identify every secret embedded in otherwise readable source or guarantee isolation from a hostile concurrent filesystem. Do not claim full credential protection or arbitrary code sandboxing. No independent Git diff or execution of tests is granted; Main supplies these and Reviewer can challenge them.

## Configuration

`runtime/opencode/opencode.json` sets `default_agent` to `vibe-main` and registers only the local V2 plugin directory at `./runtime/opencode/plugins/vibe-v2`. OpenCode 2.0.29 ignores the legacy `subagent_depth` field, so the baseline does not set it. The config intentionally does not configure model/provider, MCP, third-party plugins, or user permissions globally.

To preserve the plugin’s relative imports, stage `runtime/core/` and `runtime/opencode/` under `$OPENCODE_CONFIG_DIR/runtime/`, merge the config snippet into `$OPENCODE_CONFIG_DIR/opencode.json`, and stage the two Markdown Agents into `$OPENCODE_CONFIG_DIR/agents/`. Do not copy only the plugin file. Project files (`AGENTS.md`, `.vibe/`) normally arrive through Workbench creation (blank template or approved existing-log import) and first sync. The local package also ships the generated canonical engineering-dev template for explicit offline initialization. The blank template includes `.vibe/tasks/.gitkeep` but no registered Task or Session; actual runtime recovery creates Session files as needed. The installer is `scripts/vibe_v2_installer.py` (`install` / `verify` / `uninstall`). It merges `plugin` and `default_agent` into `opencode.json` while preserving the file's permission bits, keeps every other key, writes an owner-only backup that must be deleted after verification because it holds credentials, removes unmodified managed files that the current source no longer ships, and never deletes a managed file the user has edited.

## Known integration checks

Before release, verify in a clean OpenCode V2 environment:

- plugin loads without errors;
- `/fast`, `/balanced`, `/strict` appear and execute;
- bare commands change mode and only confirm;
- command plus trailing text both changes mode and executes the task;
- mode commands queue behind current work rather than interrupt it;
- a mode token is one-time, Session-scoped, and cannot be reused or used to select a different mode;
- mode survives compaction and reopening the same Session; differing frozen Task policy, exact recovery path and relevant evidence survive or are reacquired; no duplicate Task or reviewer launch;
- a new Session defaults to balanced;
- mode storage is isolated by Session ID;
- current Task policy remains frozen after a mode change;
- main Agent can invoke reviewer in strict mode;
- reviewer can use the locator and native read on relevant source, cannot use shell, edit, native glob/grep, web, Skill or subagents; locator rejects unauthorized child, denied read result, traversal and protected paths; verify actual host tool visibility and permission assertion in the installed build;
- reviewer is denied in fast/balanced even if the main Agent attempts to invoke it;
- reviewer is denied without a registered active Task, or when the Task is not strict / not in review / not verified;
- review permits are one-time and consumed by the permission hook;
- Task control start/resume/pause/close keeps the pointer consistent;
- missing/invalid mode storage safely defaults to balanced and does not claim a different mode.

## P0/P1 host validation boundary

The adapter uses native `permission.evaluate`, `tool.execute.after` and parent `session.context` hooks. OpenCode 2.3.0 source inspected for this repair: [native subagent](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/tool/plugin/subagent.ts) (always background, returns running), [Session schema](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/schema/src/session.ts) (terminal outcome), [message schema](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/schema/src/session-message.ts) (assistant/idle markers), and [context history](https://github.com/anomalyco/opencode/blob/v2.3.0/packages/core/src/session/history.ts). The existing synchronous v2.0.32 native completion contract remains covered. Tests drive the production adapter with simulated host APIs, not a provider-backed session. Source inspection and local green tests are not live smoke. Before rollout, run the host checklist in `evaluations/README.md` on the exact target build, including installing/reloading the revised plugin and Agent instructions.
