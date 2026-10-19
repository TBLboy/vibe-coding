# Handoff Brief for the Implementing Agent

You are taking over a clean-room Vibe Coding V2 rewrite. Your job is to refine and finish the new framework using this package as the source of truth. Do not port old implementation code or create compatibility/migration behavior.

## Read and obey

1. `AGENTS.md`
2. `docs/00-START-HERE.md`
3. `docs/11-DECISIONS.md`
4. `docs/01-PRODUCT-CONTRACT.md`
5. `docs/03-STATE-MACHINE.md`
6. `docs/04-DATA-CONTRACTS.md`
7. `docs/05-MEMORY-CONTRACT.md`
8. `docs/08-OPENCODE-INTEGRATION.md`
9. `docs/09-TEST-MATRIX.md`

## Required first actions

1. Run `npm run test:core` and preserve all passing invariants.
2. Check the actual installed OpenCode V2 version and compare its plugin, storage, command-transform, context-hook, and permission APIs with `docs/08-OPENCODE-INTEGRATION.md`.
3. Type-check or otherwise validate `runtime/opencode/plugins/vibe-v2/index.ts` against the target host API. Do not claim that syntax-only checking is type/API validation.
4. Fix any integration mismatch with the smallest possible adapter change. Do not add a database, event log, external plugin, MCP, or additional Agent to work around a missing API.
5. Run the live smoke tests in `docs/09-TEST-MATRIX.md`, including the critical “mode change queues without interrupting current work” behavior.

## Required behavior

- `/fast`, `/balanced`, `/strict` are the only mode controls; new Session defaults to balanced.
- Mode state is per OpenCode Session, not per project.
- A mode change must not interrupt the currently running action. It is queued and takes effect when the queued command is processed.
- The mode change tool must require a one-time token created by the explicit command handler. No token or a reused/mismatched token must not change mode.
- Existing Task policy remains frozen; mode applies to new work.
- Fast/balanced never invoke reviewer. Strict requires verification then reviewer `go` before Task completion.
- Strict reviewer is read-only, has no shell/glob/grep access, and cannot edit files. The plugin permission hook denies invocation without a one-time permit for the active strict Task.
- Maximum two automatic review repair rounds; then block and stop automatic retries.
- Trivial one-turn work creates no Task and no memory write.
- The Session-specific `.vibe/sessions/<session-id>/current-session.md` is recovery state; project-level `.vibe/progress.md` is durable project memory. Do not update either after every action.

## Scope limits

Do not implement an installer before live behavior passes. When an installer is eventually added, it must preserve unrelated user configuration, validate paths, back up touched files, roll back failed writes, and have install/verify/uninstall tests.

Do not add:

- legacy migration or compatibility;
- Goal runtime objects, Run state machines, Evidence entities, event sourcing, operation ledgers, SQLite projections;
- independent reviewer toggle;
- default MCP servers or third-party workflow plugins;
- parallel writing agents or a large Skills/command catalog;
- telemetry that records each action.

## Done when

- Core tests pass.
- Plugin APIs and mode persistence are validated in the actual target OpenCode V2 build.
- Mode command behavior, Task policy freezing, strict review gate, bounded retry, and memory write conditions pass the end-to-end matrix.
- Documentation has one consistent answer for every rule and contains no contradictory old workflow descriptions.
- The package explicitly distinguishes tested behavior from anything still unverified.
