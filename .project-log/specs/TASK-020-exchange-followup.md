# TASK-020 explicit snapshot exchange — implementation record

Date: 2026-09-20. Implemented in source and under isolated verification; still not a deployment authorization and still not the whole TASK-020.

The first bounded transaction/view slice left exchange disabled. DEC-007 approves explicit synchronization and its cooperating Git lock boundary, not reuse of the experimental JSON-row prototype or a claim that the entire TASK-020 passed.

## Local sequence versus immutable origin

Implemented in store schema v2. `metadata.local_revision` and every entity `*_sequence` column are the receiving repository's own ordering; `commands`/`events` additionally carry `origin_kind`, `origin_context_id` and `origin_revision`, which describe the command at its origin and never change. Receipts keep the origin coordinates in `context_id`/`revision`. Import appends new commands with fresh local sequences, rewrites entity sequence stamps through the incoming-sequence map, and advances `local_revision` without inventing a business command.

`origin_kind` is origin-stable rather than receiver-relative: a command minted in clone A stays `local` when clone B imports it, which is what makes byte-for-byte shared-history comparison across a third hop possible.

The previous self-referential audit is closed: `validate()` now replays each receipt against the authoritative task/run tables (including `task.begin` run agreement), checks that a locally minted command's `expected_revision` equals its origin revision minus one, and verifies the receipt, command and event headers agree on origin coordinates. The same replay is shared with import (`Store._verify_ledger`), so a snapshot can never be accepted into a store that would then fail its own audit.

## Implemented exchange

1. `export_bundle()` reads every portable record from one explicit read transaction; `ledger()` provides bounded traversal; extension fields travel verbatim.
2. `state_exchange.publish()` prepares payload and manifest objects before taking the lock, then under the short Git lock re-verifies HEAD/branch and that no command was accepted in the meantime, writes the pointer atomically and acknowledges the export. A caught failure abandons the pending intent; a hard kill leaves it.
3. `state_exchange.import_snapshot()` takes the same lock, validates pointer/manifest/payload hashes, project identity, descent from the recorded common base, and absence of unexported local commands, then applies the import transactionally.
4. `begin_export`/`finish_export`/`abandon_export` persist the publication intent; `acknowledge_export` refuses unless the published pointer matches the pending snapshot.
5. `state-attach` gives a fresh clone its own local database for an existing format marker.
6. Snapshot objects live in `.project-log/exchange/`, are content-addressed, written without a trailing newline, and marked `-text` so line-ending conversion cannot alter them; payload verification also normalizes CRLF.
7. A hard kill can leave `index.lock`. Vibe never deletes it and never clears the pending export automatically; recovery is an explicit operator step.

## Independent review outcome and fixes

Independent verification of snapshot `17c1fca9…` ran 213 assertions: 204 passed and 9 defects were raised (D1–D9). All nine are now addressed in source.

1. D1 — a hash-consistent snapshot whose entity tables disagreed with its ledger was accepted, after which the store failed its own audit and propagated the phantom entity to further peers. Fixed: `apply_import` runs the shared ledger replay before `commit`, raises `invalid_snapshot`, and the transaction rolls back byte-identically.
2. D2 — a new command whose receipt contradicted its request was copied verbatim. Fixed by the same replay.
3. D3 — accepting a command while `pending_kind='export'` made `validate()` report corruption. Fixed: the invariant is `0 < pending_revision <= local_revision`, which matches `finish_export()` semantics.
4. D4 — `state-export` reported failure after the exchange had already published, and a missing generated view file could never be repaired in place. Fixed: `publish_snapshot` isolates projection errors as `projection_error` while keeping the completed exchange, and `state_views.publish` rebuilds missing generated files (reported in `repaired`) while still failing closed on bytes that differ.
5. D5–D9 — documentation and record drift: the "export/import not available" claim in `docs/USAGE.md`, the stale ledger/entity and CLI statements here, the over-claim in `TASK-020.md`, and the stale verification counts in the session summaries.

Regression tests were added for D1–D4 (`test_state_exchange.py`, `test_state_service.py`) and proven load-bearing by re-running them against a reverted copy of the fix, where all of them fail. Windows re-run after the fixes: state 39/39, exchange 15/15, gate/metadata/integration green.

## Remaining before TASK-020 can be called done

1. Independent re-review of the fixed revision (the first review covered `17c1fca9…`; adversarial and interruption checks must be repeated against the new snapshot, and a serial fallback is weaker and must be labelled as such).
2. Branch-context coverage: `state-attach` currently refuses a context that already has a database, and there is no cross-branch migration story yet (TASK-025).
3. Ledger-versus-entity consistency is now audited for every command, including `goal.create`, and enforced at import; the remaining audit limits are the ones recorded in the review report (in-range `created_sequence`, free-text title/extensions, and a `base_snapshot` swap).
4. Legacy migration handoff, risk routing, evidence applicability, completion gates and real installation remain TASK-021..027.

## Retained limits

The exchange is reachable through the `vibe.py` subcommands documented in `docs/USAGE.md` (`state-attach`, `state-export`, `state-import`, `state-exchange`, `state-exchange-finish`, `state-exchange-abandon`). No legacy project is converted; no real global profile or paper data is modified. Completion remains `implemented-unverified`. TASK-021 risk routing, TASK-022/023 evidence semantics, TASK-024 reviewer gates and TASK-025 migration remain dependent work, not functionality supplied by the initial store/view slice.
