# Vibe Coding V2 Engineering Pack — 0.1.0 Baseline

Release date: 2026-10-18

## Purpose

This is the first clean-room engineering baseline for the Vibe Coding rewrite. It is intentionally small and is designed to be refined further by an implementation Agent.

The package does **not** preserve or migrate any previous framework architecture, state, Goal/Run/Evidence graphs, operation ledger, SQLite projection, default MCP bundle, or legacy workflow compatibility.

## Locked product decisions

- Four first-class concepts only: Session, Policy, Task, Project Memory.
- One lifecycle with three policies: `fast`, `balanced`, `strict`.
- No independent reviewer toggle.
- `fast` and `balanced` never invoke reviewer.
- `strict` always creates a Task and cannot complete without reviewer `go`.
- Task policy freezes at Task start; Session mode changes affect new work only.
- Verification is required for code delivery, but verification depth is risk-based.
- Project memory stores future-useful facts, not command/file-read/retry transcripts.
- Fast/balanced do not force Task creation for trivial work.
- Memory writes are event/value driven, not ritual writes after every operation or task.

## Included

- Product and architecture contracts under `docs/`.
- Minimal Task JSON schema.
- Pure TypeScript reference core for mode policy, Task policy, Task state machine, memory policy, and strict review authorization.
- OpenCode V2 adapter baseline with `/fast`, `/balanced`, `/strict` command registration, Session-scoped mode storage, Task control, and strict reviewer authorization gate.
- Conservative `install` / `verify` / `uninstall` utility with isolated tests for preserving user config, preserving post-install user edits, and repeated-install ownership.
- Primary `vibe-main` Agent contract.
- Read-only strict-only `vibe-reviewer` Agent contract.
- Project `AGENTS.md` template.
- Core behavior and package-shape tests.
- Handoff brief for the next implementation/refinement Agent.

## Verification performed for this release

- `npm run test:core`: 37/37 tests passed (line endings normalized for CRLF checkouts).
- `python -m unittest scripts/test_vibe_v2_installer.py -q`: 4/4 tests passed for user-config preservation, post-install modified-file preservation, repeated-install ownership/uninstall restoration, and Python bytecode-cache exclusion.
- One-shot `npm exec --yes --package typescript@5.9.3 -- tsc --noEmit -p tsconfig.core.json`: passed without adding a project dependency.
- Baseline typecheck was reported as passed when the pack was prepared; the current refinement environment has no local/global `tsc`, so `npm run typecheck:core` is currently **environment-blocked** rather than claimed passed.
- Static consistency scan performed across README, AGENTS, docs, runtime, schema, and tests.
- OpenCode V2 API usage was compared against the current official V2 documentation for plugin definitions, command/tool transforms, storage, Session hooks, permission hooks, Agent modes, and ordered permissions.
- OpenCode **2.0.29** isolated smoke loads `vibe-coding-v2` from the local plugin directory and registers `/fast`, `/balanced`, and `/strict`. A provider-backed OpenCode **2.0.32** live smoke consumed a `/fast` one-time token and completed a persisted strict Task through review authorization, `vibe-reviewer` `go`, and Task close. This is targeted smoke evidence, not a general V2 compatibility claim.

## Not yet acceptance-tested

- Provider-backed `/balanced` command continuation.
- Negative reviewer-permission enforcement: no permit, wrong Task state/policy, and attempted edit or arbitrary shell action.
- Real Session location behavior after moving/forking Sessions/worktrees.
- Full fresh-install/recovery acceptance matrix beyond the isolated installer tests and the current live control-layer deployment.

Do not call this production-ready until the live smoke-test checklist in `docs/08-OPENCODE-INTEGRATION.md` and `docs/09-TEST-MATRIX.md` passes on a pinned OpenCode V2 version.

## Recommended next work

1. Pin a concrete OpenCode V2 build and run the live smoke matrix.
2. Fix adapter mismatches discovered by the live test without changing the product contracts unless necessary.
3. Complete the remaining negative reviewer-permission, recovery, compaction, and cross-Session smoke tests.
4. Keep default dependencies/MCPs at zero unless a concrete requirement justifies one.
