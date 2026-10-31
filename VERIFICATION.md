# Verification Snapshot

Date: 2026-10-29
Version: 0.1.0

## Local executable checks

- `npm run test:core` — PASS, 47/47 tests.
- `npm run test:py` — PASS: installer 6/6 (user-config preservation, modified-file preservation, repeated-install ownership, bytecode exclusion, config-mode preservation + owner-only backup, stale managed-file removal), project init 7/7 (incl. rule 1 = 点拨 mentoring rule, contiguous numbering), project archive 3/3, configure_models 3/3.
- `npm run typecheck:core` — PASS via one-shot `npm exec --package typescript@5.9.3` (no project dependency added).
- `npm run verify` — PASS (`test:core` + `test:py`).

## Static package checks covered by tests

- no legacy migration/upgrade entrypoints;
- no default third-party MCP/integration bundle;
- Task schema excludes Goal/Run/Evidence graph concepts;
- fast/balanced policy text prohibits reviewer;
- strict reviewer requires an authorized active strict Task, and strict close requires an observed reviewer invocation;
- Task records are structurally validated before any control transition;
- one memory root per project is resolved from the Session directory and injected with the registered Task;
- reviewer Agent is read-only by permission policy;
- memory policy does not force writes for trivial completed work;
- managed Skills carry complete methodology and per-work requirement baselines.

## Live acceptance boundary

- Earlier live smoke (OpenCode 2.0.29 / 2.0.32): plugin loads, `/fast` `/balanced` `/strict` register, a provider-backed `/fast` consumed its token, and a provider-backed `/strict <task>` ran verification → permit → `vibe-reviewer` → `go` → close.
- Current local use (OpenCode 2.0.32 desktop): Session policy injection, `vibe_task_control` start/close, Skill discovery and installer verify are exercised daily by the framework's own development Sessions.
- Still unverified live: memory-root resolution from a sub-repository Session, the reviewer-invocation close gate on a real strict run after this change, mode persistence across compaction/reopen, cross-Session isolation, frozen-policy-after-mode-switch, and negative reviewer permission cases. Run these before calling the package production-ready.
