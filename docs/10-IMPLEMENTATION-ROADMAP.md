# Implementation Roadmap

This is the recommended order for the Agent refining the package. Do not build every subsystem at once.

## Phase 1 — Lock core behavior

- Run pure core tests.
- Resolve type/runtime errors in the mode, task policy, memory policy, and task state machine.
- Add tests for every invariant before adding new features.

Exit condition: core tests pass; the three modes have unambiguous behavior; no old concepts are required.

## Phase 2 — OpenCode mode integration

- Validate the plugin API against a pinned OpenCode V2 version.
- Verify the three explicit mode commands, per-session storage, context injection, and compaction/reopen behavior.
- Fix the adapter only; do not introduce a database or a second mode source.

Exit condition: all mode smoke tests pass.

## Phase 3 — Agent policy and strict reviewer

- Validate primary/subagent definitions and permission rules.
- Confirm fast/balanced never invoke reviewer.
- Confirm strict reviewer is read-only and strict cannot complete without `go`.
- Verify the two-repair-round limit and blocked escalation.

Exit condition: live review matrix passes.

## Phase 4 — Project Memory and recovery

- Use the provided `.vibe` templates.
- Validate conditional Task creation and the two memory write triggers.
- Test recovery from implement, verify, review, and blocked phases.

Exit condition: recovery works without an operation ledger or database.

## Phase 5 — Packaging

Only after the runtime behavior is stable:

- add a minimal installer that stages `runtime/core/` and `runtime/opencode/` together so plugin-relative imports remain valid, and stages the Agents separately;
- snapshot and preserve existing user configuration;
- validate destination paths and symlink boundaries;
- provide backup and rollback;
- test install, verify, repeated install/update ownership, and uninstall on a clean profile;
- pin dependencies and document the supported OpenCode version.

Exit condition: clean install and rollback acceptance passes on supported platforms.

## Explicit non-goals for the first pass

No MCP bundle, Goal plugin, general Skills marketplace, dynamic subagent orchestration, parallel writers, operation ledger, SQLite, analytics dashboard, autonomous background loop, compatibility shim, or old-state migration.
