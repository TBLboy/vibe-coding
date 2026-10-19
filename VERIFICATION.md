# Verification Snapshot

Date: 2026-10-19
Version: 0.1.0

## Local executable checks

- `npm run test:core` — PASS, 36/36 tests.
- `python -m unittest scripts/test_vibe_v2_installer.py -q` — PASS, 3/3 tests: user-config preservation, post-install modified-file preservation, and repeated-install ownership/uninstall restoration.
- One-shot `npm exec --yes --package typescript@5.9.3 -- tsc --noEmit -p tsconfig.core.json` — PASS without adding a project dependency.
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

- OpenCode 2.0.29 isolated-profile smoke: `vibe-coding-v2` loads from the local plugin directory, and `/fast`, `/balanced`, and `/strict` register successfully.
- Current live control layer smoke: OpenCode 2.0.32 reports `vibe-coding-v2` active; all three mode commands are registered; V2 verification passes; legacy Vibe state/runtime is absent; the pre-existing model, three providers, and eight MCP entries remain present.
- A provider-backed `/fast` command consumed its one-time token and the main Agent confirmed the new mode without starting work.
- A provider-backed `/strict <task>` smoke created a strict Task, passed task-record verification, obtained a one-time review permit, invoked `vibe-reviewer`, received `go`, and closed the Task. The persisted Task ends as `completed` / `complete` with `verification=passed` and `review.verdict=go`.
- The full fresh-install/recovery matrix remains unverified. So do model-driven `/balanced`, mode persistence across compaction/reopen, cross-Session isolation, frozen-policy-after-mode-switch, and explicit negative reviewer permission cases (no permit, non-strict Task, edit/shell attempt).
- Do not treat the package as production-ready until the remaining live matrix passes.
