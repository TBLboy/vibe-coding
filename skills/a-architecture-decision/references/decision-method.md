# Architecture decision method — worked example

Use as a reasoning example, not a required design or template.

## Case: add a second delivery transport

Current service owns order status, uses one HTTP sender, and retries only transient errors. Approved requirement: also deliver to a local queue; preserve deduplication and existing HTTP defaults. A third transport is hypothetical. Source evidence: trace `submit → service → HTTP sender`, status writes and retry classification. Unknown: queue acknowledgement semantics. Non-goal: external plugin ecosystem.

Drivers: no duplicate order on retry (hard invariant); old HTTP configuration remains valid (hard contract); transport changes should not change order ownership (maintainability); overhead and operational burden are preferences unless a budget is agreed. Example quality scenario: after acknowledgement is lost, a repeated request with the same idempotency key must not create a second order; verify with a fault-injection integration test.

| Option | Benefit | Cost and risk | Disposition |
|---|---|---|---|
| Local branch at sender boundary | Small, quick, no registry | If both callers repeat retry logic, drift | Viable if variation is genuinely small |
| Narrow transport port with two adapters | Hides protocol differences; one retry policy | Adapter error semantics need explicit contract | Prefer if concrete variation is demonstrated |
| Dynamic plugin registry + separate service | Independent extension/deployment | Discovery, lifecycle, trust and deployment complexity | Defer absent approved requirement |

Decision: service remains sole order-state owner; sender returns a bounded outcome (`accepted`, `retryable`, `terminal`, `unknown`), never writes order state. Preserve old config default; queue adapter may need a spike to establish acknowledgement/idempotency properties. If an existing externally visible error contract must change, obtain C approval. Record why smaller/larger alternatives were rejected; do not claim queue deduplication until measured.

Trace success and failure: submit → owner validates key → sender → acknowledgement → owner commits; lost acknowledgement → owner retains uncertain state → retry/reconcile under approved deduplication contract. If the external system cannot support that invariant, revisit the design instead of promising exactly-once delivery.

Handoff: implement transport boundary and characterization tests for HTTP first, then queue adapter and integration, then opt-in config. Verify the production entrypoint, failures and rollback. This is a design decision, not a claim that the implementation works.

## Sources for deeper study

- [SEI Architecture Tradeoff Analysis Method](https://www.sei.cmu.edu/library/the-architecture-tradeoff-analysis-method-collection/) — quality scenarios and competing attributes; this Skill adopts a lightweight subset, not full ATAM.
- [Martin Fowler, Parallel Change](https://martinfowler.com/bliki/ParallelChange.html) — staged incompatible interface evolution.
