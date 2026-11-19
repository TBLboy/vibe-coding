# Controlled engineering change — worked example

Case: add a queue transport to an existing HTTP delivery service. Approved: new transport opt-in; default HTTP behavior, error classification and order deduplication retained. No new plugin ecosystem or default change.

## Change/preservation ledger

| Capability / contract | Before | Planned disposition | Verification |
|---|---|---|---|
| Default delivery | Config absent → HTTP | Preserve; same entrypoint | Old-config integration test |
| Timeout classification | Timeout → retryable | Preserve; move to adapter mapping if needed | Failure injection through entrypoint |
| Order state | Service owns state writes | Preserve | Duplicate request and failure state test |
| Queue delivery | Not available | Add; explicit config and registration | Actual configured route + response |
| Private HTTP helper | Called by service | Replace if necessary; trace old duties | Characterization tests and caller review |
| Public legacy import | Unknown downstream clients | Preserve until migration approved | Import/consumer test, disclose external unknown |

The ledger is not proof. Locate real call sites and confirm each row in the current checkout. A change to a public contract or product behavior requires C authority even if local tests pass.

## Slice and reconcile

1. Run existing focused tests, add tests locking intended default, timeout and deduplication where missing. Record baseline failures separately.
2. Isolate protocol-specific behavior behind the smallest appropriate boundary; old tests continue to pass. Verify real service invocation, not just adapter calls.
3. Add queue implementation plus actual config/wiring and failure mapping as one coherent slice. Add positive and negative integration tests. Keep opt-in default.
4. Review actual diff against non-goals and ledger. Forward: follow queue config to side effect. Backward: start from each old contract, including failures and deleted duties; trace to implementation and test. Check migration/rollback and unrelated work.
5. Bind final covered artifacts and run verification. If queue hardware/service is essential but unavailable, report missing evidence; do not equate a fake queue with actual deployment success.

A local typo fix can do the same reasoning inline in seconds. Do not create a persistent ledger file or a new workflow phase just because this example uses a table.

Further reading: [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html) for expansion, migration and contraction of an interface. Use when incompatibility warrants it, not for every refactor.
