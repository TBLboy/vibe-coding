# Workflow optimization implementation contract

Date: 2026-09-19. Scope: TASK-014 through TASK-027; decision DEC-006.

## Execution boundary

The user has explicitly started implementation of the full four-objective plan. The previous planning-only pause is superseded. Native thread Goal remains active until the entire approved outcome has evidence. A successful early repair does not complete that Goal.

All test execution, fixture projects, temporary CODEX_HOME profiles, caches, build output and reports belong under D:/Project/vibe-coding-validation. Do not run tests from the source tree. Do not use D:/Project/my_lunwen as a mutable fixture. Existing source-tree artifacts predate this work; do not delete unrelated files to manufacture cleanliness.

Source modifications and durable .project-log records are permitted. Validation copies include the changed source but exclude .git, caches and generated builds. Capture a source digest manifest before each run and detect unexpected changes. Logs may change through the installed Hooks and must be distinguished from source/test pollution.

Real global installation and actual project data migration retain TASK-027's separate target-specific approval gate. All earlier installation exercises use isolated profiles. No automatic git commit/push, model/provider change, destructive cleanup, or background daemon.

## Frozen behavioral requirements

### WF-1: trustworthy recovery (BL-WFOPT-001)

Goal defines the delivery contract; Task defines one verifiable outcome; Run is an execution of a specific Task. An unbound Task must not inherit a completed historical Goal through a fallback read. Requirement IDs are not Goal IDs.

Tasks have pending/running/waiting-user/blocked/done/cancelled states; Runs additionally support handed-off. Existing in-progress/complete representations are mapped explicitly at compatibility boundaries. A blocking user fact requires a question reference and a concrete resumption condition. Environment/dependency blockage is not automatically waiting-user.

Selecting a new task must preserve or close the previous execution context. Blocking, resuming and completing a task update relevant Run state in the same authoritative transaction. Goal completion rejects unfinished tasks in its own scope; it does not force-complete them. An independent task can run while another waits for user facts.

Restore is read-only and reports state_conflict for contradictory legacy input. Repair first produces a plan and requires revision checking; it does not choose business truth by modification time. Querying state does not create projects or append business events.

### WF-2: record once (BL-WFOPT-002)

One accepted operation owns all resulting Task/Run/blocker/evidence/event changes. command_id plus canonical payload identity makes retries idempotent. Reusing an ID with a different payload is a conflict. expected_revision prevents lost updates.

Use short transactions: no subprocess, model call, PDF compilation or large-file hashing while holding the write transaction. A committed operation survives failed view generation. Retry returns the original receipt and repairs pending projections without duplicating evidence or events.

SQLite is the first prototype, not yet a mandatory migration. Compare one atomic JSON document as a bounded reference. G1 requires independent assessment of interruption behavior, command idempotency, concurrency and Git exchange before production integration.

Markdown views contain source revision and are rebuildable, never concurrent business authorities. User-authored notes remain separate. Multi-file export publishes a hash manifest last; readers reject incomplete/mixed snapshots. Export failure reports local-saved/export-pending.

Git exchange uses immutable project identity, versioned snapshots and common-base checks. A local revision integer is not a global clock. Reject conflicting unexported changes, ambiguous branches and foreign project identity rather than last-write-wins. Re-importing the same snapshot is harmless. Branch A/B/A must not discard local work. Ordinary external git push is not falsely claimed to be transactionally controlled by this framework.

### WF-3: proportional execution (BL-WFOPT-003)

Classify after minimum mandatory project/safety context, before loading bulk history. Consultation does not create an engineering Run. Quick changes still receive a compact record and relevant verification, but no automatic Goal, architecture, decision, trace or independent-review artifact.

Policies quick/standard/strict have versioned reason codes, required checks and escalation conditions. Scope size is not risk. Changes to scientific conclusions, security, public contracts or formal submission constraints require strict handling. Unknown noncritical facts can use standard; unknown critical semantics require clarification. Actual changed scope is checked against the declared scope before finishing.

Task context returns relevant acceptance, blockers, decisions and evidence, normally within an 8 KiB trial budget. Required safety and blocking facts are never silently truncated. Additional information is available by ID. Strict work reuses applicable evidence, not unrelated checks or generic all-project recompilation.

### WF-4: version-aware evidence (BL-WFOPT-004)

Historical result (passed/failed/inconclusive) is immutable; applicability (current/stale/missing/unknown/historical) is relative to an explicit target context. Completion accepts passed AND current AND matching acceptance coverage. A historical completed Goal remains a historical fact; a new deliverable requires applicable evidence.

Phase one selectors are raw-file, explicitly approved text-lf and versioned JSON fields. Always retain original byte hashes. text-lf only changes CRLF into LF for declared text formats; it does not normalize arbitrary spaces, comments, symbols, Unicode or binary output. Missing files do not prove the old test failed. Selector failures or undeclared dependencies are unknown, not current.

Git diff is hashed from exact bytes without stripping or decoding. Diagnostic strings may be decoded with replacement but never enter fingerprints. Git command failure must not become an empty-diff success. Non-Git directories and unborn repositories can use file hashes with null commit/diff; valid repositories whose Git commands fail must surface an error. Git access must be read-only and disable external diff/text conversion.

Dependencies distinguish input sources, generated artifacts and diagnostics. File hints from Hooks are advisory, not authoritative. Completion independently verifies required input fingerprints to catch shell/manual/checkout changes; mtime and size alone cannot prove currency. Detect changes during validation instead of claiming cross-file atomicity.

Review records bind a distinct reviewer, acceptance scope and inspected version. Same-agent role switching is an explicitly degraded check, not independent review. Missing reviewers never create synthetic successful review events. Review currency follows the inspected version.

## Environment and compatibility

Configured runtime interpreter is an absolute, existing Python 3.11+ executable selected through VIBE_PYTHON or CODEX_HOME/vibe-python. Explicit invalid configuration fails visibly rather than falling through PATH or WSL. Runtime launch performs no environment installation. First-install bootstrap may discover Conda, but cannot require a nonexistent py launcher to perform that discovery.

PowerShell and Unix adapters forward argument arrays to the same Python CLI. --codex-home is consumed consistently by the launcher and installer. Strict UTF-8 structured IO is separate from arbitrary Git byte output. Missing config, invalid paths, insufficient Python version and missing dependencies have actionable errors.

Preserve legacy project initialization's non-overwrite behavior. Source-only changes do not rewrite installed global config. Existing initialization rules are not permission to silently migrate data. New-format stores reject old writers unless explicitly adapted. Unknown fields and evidence provenance survive import/export; unsupported downgrades preserve the new store and clearly report the limitation.

## Minimal external fixture inventory

| Fixture | Required observation |
|---|---|
| plain project, no Git | file hashes present; no invented commit/diff |
| Git with no commits | file hashes retained, explicit absent commit |
| changed GBK/invalid UTF-8/Unicode/binary files | exact byte diff hash, no decoding exception |
| broken Git executable/repository/access | explicit error, no successful empty diff |
| configured interpreter with spaces/non-ASCII path | correct argument forwarding |
| missing/invalid interpreter and no py/python3 | explicit diagnostic, no silent fallback |
| blocked task + completed old Goal | no active continuation or historical Goal fallback |
| interrupted transaction/projection | rollback before commit; recoverable views after commit |
| duplicate command/stale revision/concurrent writer | one receipt or clear conflict |
| two clones + A/B/A branch switch | lossless roundtrip or preserved conflict |
| CRLF source/old PDF/missing artifact | distinct applicability outcomes |
| graph with unaffected metrics and changed caption | retain metrics, recheck rendering |
| strict task with same/missing/stale reviewer | completion rejected or explicit approved downgrade |

## Completion matrix

SC-001: state invariants and Git exchange pass independent review (TASK-017..020).
SC-002: quick/standard/strict and context costs satisfy representative task trials (TASK-021).
SC-003: current evidence and review gates survive missed Hooks and input changes (TASK-022..024).
SC-004: Windows and Linux entry/installation/compatibility evidence exists (TASK-016/026).
SC-005: migration and rollback preserve post-migration writes (TASK-025).
SC-006: approved real installation and single-project trial demonstrate usability (TASK-027).
SC-007: external test isolation and independent final review are documented; source artifacts are not polluted.

This contract fixes implementation expectations, not unexecuted results. Every SC remains pending until supporting artifacts and independent checks are inspected.
