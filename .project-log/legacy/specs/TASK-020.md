# TASK-020 production landing specification — approved, implementation in progress

Date: 2026-09-20. Business atoms: BL-WFOPT-001/002. Decisions: DEC-006, approved DEC-007. TASK-019 bounded G1 disposition and Q-002 approval allow source integration and isolated tests. This specification does not authorize migration or install.

## Objective and non-goals

Make one accepted command atomically update its Task/Run/blocker state, receipt and audit record; render revision-bound summaries from that state. Read-only restoration must not create a project, mutate authority or emit business events. Continue using the configured Python 3.11+ interpreter and standard-library SQLite rather than adding an ORM/server.

Do not copy the prototype's single JSON row as the production model. Do not change native Goal controls, scientific business rules, global configuration or real project data. Semantic evidence gates, risk classification and actual migrations remain TASK-021..027. A proof_ref string in the prototype is not sufficient production completion evidence.

## Observed baseline and prototype evidence

Existing runtime/scripts/vibe.py reads multiple YAML sources; loop_state.py maintains separate state/evidence/event files. The external experiment showed state transitions, duplicate command receipts, optimistic revision checks and process-kill rollback working in Windows and Linux tests. First G1 review found a wrong-branch publication and malformed receipt import; corrected-version re-review independently reproduced both old defects, then passed eight repaired-version case groups.

Current external Windows/Linux suites each pass 32 state tests and 19 exchange tests. Independent re-review is Windows-only and explicitly approves only bounded remediation and the next design step. It is not a blanket production gate. Benchmarks showed the whole-document JSON comparator faster for the measured small synthetic workload; choosing SQLite must be justified by transactional ownership, indexed queries and bounded updates, not an unmeasured speed claim.

## Proposed ownership and interfaces

Keep argparse in vibe.py. Add narrowly scoped state-service, repository and view-rendering modules; final filenames may follow existing code conventions. loopctl.py routes supported writes to the same service for explicitly migrated projects, not a second writer. Existing projects remain on the legacy adapter until an explicit migration passes.

Proposed operation envelope: schema_version, command_id, expected_revision, action, payload. Response: original immutable receipt plus current projection/snapshot publication status. command_id is unique within immutable project identity. Repeated identical requests return the original receipt; changed action/payload conflicts. Local revision is not a global clock, and import does not rewrite historical receipt revisions.

Queries expose current task, by-ID detail and bounded related context. They must not read the whole event history for ordinary status. Contradictory legacy inputs produce state_conflict with an explicit repair plan, not a timestamp-selected winner.

## Proposed local schema

- metadata: schema version, immutable project identity, local revision and branch/worktree binding.
- goals/tasks/runs/blockers: keyed entities with explicit foreign relationships and status constraints; preserve uninterpreted extension fields separately.
- commands/events: unique command identity, canonical action/payload digest and immutable receipt; event headers must agree with receipts.
- projection_jobs: latest committed revision requiring view refresh, independent of business completion.
- exchange_contexts: common-base snapshot, exported source revision and pending publication receipt.

Use parameterized queries, foreign keys and short explicit transactions with bounded busy timeout. A transaction inserts the receipt and event and updates only affected entities. Tests must demonstrate bounded reads/writes; normalized tables alone are not proof of efficiency. Defer evidence/dependency tables until their task-specific schema is specified.

## Concurrency and lifecycle

Resolve and validate operation shape before entering the write transaction. No subprocesses, compilation, PDF work, model calls or input hashing inside it. Verify expected_revision after writer acquisition. On exception before commit, nothing is accepted; after commit, a view/export failure must not roll back or duplicate the accepted operation.

An unfinished Goal cannot finish by silently completing its tasks. Task waiting-user requires a referenced question and resumption condition; dependency/environment blockage stays distinct. Switching work closes or hands off the previous execution explicitly. An independent task can run while another waits. Unbound tasks never inherit completed historical Goals.

## Approved Git coordination boundary — Q-002

Recommendation: explicit snapshot export/import only in the first release. Routine task commands, evidence operations and queries do not take Git's index lock or auto-export after every tool call. On explicit exchange, precompute content outside the Git critical section where possible, acquire the worktree index lock exclusively, revalidate project/worktree/branch/store plus source revision and common base, then publish and acknowledge briefly. No automatic git add, commit, push or branch switch.

The prototype experimentally holds the lock longer while preparing objects; shortening that section and interruption tests are required before production. Ordinary cooperating Git operations may report busy during exchange. Direct Git plumbing or manual metadata edits that bypass the index lock are outside the guarantee. A killed process can leave an index.lock; this cannot be fixed by blindly deleting it or trusting a PID alone.

Production diagnostics must show the exact lock path, ownership token, pending export identity and last accepted state revision. An explicit recovery procedure must require operator confirmation after checking no active Git/Vibe writer and preserving pending authority. Foreign or unrecognized lock bytes are never removed by Vibe. No automatic stale-lock cleaner is proposed.

The user accepted this Git interlock cost in Q-002. Do not replace the approved boundary with last-write-wins or claim arbitrary external checkout is atomic. Production exchange still requires its own implementation and interruption/concurrency verification before use; approval is not evidence of implementation.

## Views, errors and observability

Generate current-session/progress/handoff from one committed state revision, latest summary first. User-authored notes live outside generated sections. View publication failure leaves a pending job; retry repairs output without duplicate events. Because generated content is a pure function of the revision, a missing generation, manifest or view file is rebuilt in place on the next publication (reported as `repaired`), while bytes that exist and disagree are rejected instead of overwritten. Readers reject mixed/incomplete multi-file snapshot manifests. No unbounded repeated full-history regeneration on each tool call.

Return distinct diagnostics for invalid input, stale revision, mismatched command payload, state conflict, busy writer, missing/foreign snapshot, incomplete publication and interrupted projection. Log compact operation ID, result, revision, elapsed time and outcome; no secrets, author details or full unrelated source contents in synthetic tests. Import validates content hashes and entity/receipt semantics before writing: the incoming ledger is replayed against the incoming entity tables and every receipt is re-derived from its request, run and entities, so a snapshot that would fail the store's own audit is rejected as `invalid_snapshot` with no byte changed. A command accepted while a publication intent is pending is legal and must leave the audit clean; `pending_revision` may lag `local_revision`. Shared historical commands/events remain immutable.

## Compatibility, rollout and rollback

Enable new-state writes only for explicitly initialized/migrated test fixtures until TASK-025 validates import and lossless rollback. Format markers route all write paths; unsupported old writers must fail rather than updating stale YAML. Existing initialization must retain its non-overwrite behavior. No eager rewriting of every old project or installed profile.

Keep old source snapshots and migration manifests. Rollback must preserve post-migration commands and evidence, not merely restore a pre-migration backup. Actual user installation and my_lunwen trial require TASK-027 target-specific permission and Q-001 interpreter-repair policy.

## Acceptance matrix

All execution in D:/Project/vibe-coding-validation, using source snapshots and before/after source digests:

1. Same-command retry, changed payload conflict, stale revision and two writers; receipt/event identity consistency.
2. Begin/block/resume/handoff/finish/cancel; task/run linkage and explicit Goal scope.
3. Kill or fault before commit, after commit and during view publication; no half-state or duplicate records.
4. Status/context query reads bounded entities, not the complete event log; 38/500/2000 synthetic task trials report actual costs.
5. Explicit exchange with same-project common base, two clones, A/B/A, worktrees, dirty local state and unknown fields.
6. Concurrent cooperating checkout, acquisition/publication/recovery context drift, foreign/stale locks, and pending export plus later accepted commands.
7. Canonical-payload/receipt tamper, historical rewrite, incomplete or foreign manifests; rollback on rejection.
8. Existing legacy behavior, PS5/PS7/Linux adapter matrix, malformed encoding and package/project checks.
9. Independent affected-scope review and raw failure preservation. All required conditions must pass before marking TASK-020 done.

## Open decisions

Q-002 is answered by the user's explicit approval. Q-001 still blocks later actual environment repair/installation, not isolated implementation. No planned CLI or schema here is advertised as verified until its affected-scope tests and review pass.

## Incremental integration boundary

The first source slice exposes an explicitly experimental, new-fixture-only transaction service. Legacy projects are never implicitly converted. Generated views initially live in revision-bound immutable directories, outside user-authored Markdown, with one atomic manifest pointer; existing Markdown projection wiring waits for migration. Snapshot import/export is fail-closed until the remaining exchange integration and independent tests land. This slice alone cannot satisfy the full TASK-020 acceptance matrix. Completion returns implemented-unverified, never done, until evidence/reviewer gates land.
