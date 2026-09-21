# TASK-020 transaction/view slice checkpoint

Date: 2026-09-20. Status: bounded slice implemented and tested; TASK-020 remains in-progress. No installation, migration, commit or push.

## Authority and scope

The user approved Q-002; DEC-007 is active and TASK-019's bounded G1 disposition allows source integration. Q-001 remains unresolved for later actual interpreter repair/installation. The native Goal was observed usageLimited and was not resumed, completed or otherwise changed by the agent.

New source: `state_store.py`, `state_views.py`, `state_context.py`. Existing vibe/loopctl/init/validation/Hook entry points route or reject format-2 operations. Ordinary legacy projects are unchanged. New state is explicitly experimental and only initialized in isolated fixtures.

Implemented: normalized SQLite entities, short multi-entity transactions, exact immutable command receipts, optimistic revisions, explicit Goal scope, wait/handoff/resume semantics, bounded status reads, revision-bound generated views, post-commit pending repair, and prevention of legacy authority writes in format-2 projects. `task.finish` produces implemented-unverified, never done.

Not implemented: production Git snapshot exchange, independent-origin receipt import, risk routing, evidence applicability/dependencies, completion/reviewer gates, lossless migration, global installation. Remaining exchange constraints are in `specs/TASK-020-exchange-followup.md`. The local-only ledger validator is not an import verifier.

## Main-agent isolated evidence

All commands use copied source and fixtures under D:/Project/vibe-coding-validation, configured Python with -B, external profile/temp paths. Source byte digests before/after are equal in Windows harness reports.

- runs/state020-v5: 25 Windows behavioral tests passed; 38/500/2000-task benchmark passed. Ordinary status returns 10 tasks using 39 traced SQL statements at each size; it does not scan event history. This is bounded-query evidence, not proof SQLite outperforms JSON.
- linux/runs/state020-v3: 25 methods executed, 24 passed and 1 Windows-only skip; package and project checks passed on WSL Ubuntu with isolated Python 3.11.
- runs/state020-crashes-v1 and linux/runs/state020-crashes-v1: three real process-kill cases each passed, before commit, after commit and before manifest pointer publication. Retained lock after a killed publisher is refused without automatic deletion. These checks do not simulate power loss or network filesystems.
- runs/state020-regression-v3: legacy baseline, Git binding and Windows launcher regression; exact final outcomes in report.json. Baseline executes 41 tests with one existing skip, not 41 passes plus a skip.
- runs/state020-metadata-v2: package, project and loop metadata checks passed before this checkpoint update; final metadata must be revalidated after recording it.

## Failures preserved and corrections

- state020-v1: test harness omitted mandatory explicit goal_id:null and leaked its own SQLite connections; corrected without weakening production input validation.
- state020-v2: actual Windows deep-path view publication failure. Store and Views now normalize native extended-length paths. The accepted command remained committed throughout.
- state020-v3: behavioral checks passed but the harness's generic temporary-directory cleanup could not remove its long-path fixture. Subsequent runs retain that fixture externally; this is not a product-success claim for the failed cleanup run.
- state020-metadata-v1: checkpoint used unsupported architecture status accepted; corrected to existing active enum, not by changing the schema.
- reviewer-020/REPORT-v4.md: independent NO-GO found missing-marker fallback to legacy writes, a junction alias bypass, and nested non-Git Hook initialization. All three corrected in the v5 snapshot; old snapshots and failure reports retained.
- Concurrent Windows readers can temporarily prevent atomic pointer replacement. Independent probe confirms old generation remains valid, business receipt is retained, pending repair succeeds after reader exit. Pending is not relabeled successful publication.

## Independent scope

Reviewer is native agent 01a0bf00-7f09-74c1-8446-a3f743631e7a, not the implementation agent. Independent v5a suite passed 23/23 affected-scope methods after reproducing the old failures. Its final report and file hashes govern the bounded disposition, not this summary alone. Reviewer evidence is Windows-only; main Linux checks are reported separately.

## Precise continuation

Keep TASK-020 in-progress. Before adding production exchange, separate local commit revision from immutable originating command revision/context and close the receipt/run relationship audit limitation. Then implement explicit snapshot publication/import with common-base, branch/worktree binding, pending recovery and adversarial tests. Do not enable completion on proof_ref alone or install into my_lunwen/global profile.
