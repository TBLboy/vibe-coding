# Instructions for the Agent Refining Vibe Coding V2

This repository is a clean-room rewrite. Treat the current documents and source as the new baseline. Do not inspect or port old framework code unless the user explicitly asks for a focused comparison; do not create compatibility or migration work.

## Read first

1. `docs/00-START-HERE.md`
2. `docs/01-PRODUCT-CONTRACT.md`
3. `docs/11-DECISIONS.md`
4. `docs/02-ARCHITECTURE.md`
5. `docs/03-STATE-MACHINE.md`
6. `docs/04-DATA-CONTRACTS.md`
7. `docs/08-OPENCODE-INTEGRATION.md`
8. `docs/09-TEST-MATRIX.md`

## Hard constraints

- Keep the four-concept model: Session, Policy, Task, Project Memory.
- No independent reviewer toggle. Only strict invokes reviewer; fast/balanced must not create or invoke review artifacts.
- Freeze Task policy when the Task starts. Session mode changes affect new work only.
- Do not add a Goal runtime, Run state machine, event ledger, SQLite projection, standalone Evidence model, or operation transcript.
- Do not force Task creation for trivial one-turn work in fast/balanced.
- Do not force memory writes after every task. Record only future-useful facts.
- No third-party dependencies or MCPs in the default baseline. Add a dependency only after identifying a concrete requirement and obtaining approval.
- Do not change provider, model, permission, MCP or unrelated user configuration as part of this framework.
- Do not claim OpenCode integration is verified until the target build has passed the live smoke tests.

## Working method

- Make the smallest coherent change.
- Keep one canonical source for each rule. README summarizes; detailed contracts live in `docs/`.
- If documents conflict, fix the conflict at the canonical source and update dependent summaries/tests. Do not leave two contradictory rules and add a note to explain them.
- Every new behavior needs a test or an explicit reason why it cannot be tested at this layer.
- Before finishing, run `npm run test:core`, inspect the diff, and update `docs/09-TEST-MATRIX.md` if coverage changed.
- If an unresolved product choice is necessary, ask one focused question. Otherwise continue without asking the user to re-approve decisions already locked in `docs/11-DECISIONS.md`.
