# Verification Snapshot

Date: 2026-10-18
Version: 0.1.0

## Local executable checks

- `npm run test:core` — PASS, 36/36 tests.
- `npm run typecheck:core` — ENVIRONMENT-BLOCKED: no local or global `tsc` is available in the current refinement environment.
- `npm run verify` — NOT RUN: it includes the environment-blocked typecheck step.

## Static package checks covered by tests

- no legacy migration/upgrade entrypoints;
- no default third-party MCP/integration bundle;
- Task schema excludes Goal/Run/Evidence graph concepts;
- fast/balanced policy text prohibits reviewer;
- strict reviewer requires an authorized active strict Task;
- reviewer Agent is read-only by permission policy;
- Task completion requires verification and strict review `go` where applicable;
- Session-scoped mode, active-Task pointer, review permit, and recovery-path behavior;
- memory policy does not force writes for trivial completed work.

## External API alignment checked

The adapter was compared with the current OpenCode V2 documentation for:

- `Plugin.define` plugin shape;
- command and tool transforms;
- plugin-scoped storage;
- Session context hooks;
- permission evaluation hooks;
- V2 Agent `primary`/`subagent` modes and ordered permission rules.

## Live acceptance boundary

- Target smoke build: OpenCode 2.0.29.
- Isolated profile loads `vibe-coding-v2` from the local plugin directory as an active plugin.
- `/fast`, `/balanced`, and `/strict` register successfully.
- A real isolated Session accepted and queued bare `/fast` and `/strict` commands.
- Provider-dependent model continuation after `vibe_set_session_mode`, strict reviewer invocation/permission enforcement, persistence across compaction/reopen, and installation remain unverified.
- Do not treat the package as production-ready until the remaining live matrix passes.
