# Verification design — worked example

## Green tests, wrong subject

Requirement: only `prepare → implement → verify` is legal; rejected transitions leave persisted state unchanged. A pure `transition(state, event)` function enforces it, but the production endpoint writes the requested state directly. Pure-function tests pass. The actual risk is not a missing transition function; it is bypass of the owner by the production ingress.

| Claim | Failure hypothesis | Target / fixture | Oracle |
|---|---|---|---|
| Legal transition persists | Handler ignores owner or write fails | Real endpoint + isolated in-memory/test store | Return and persisted state both equal `implement` |
| Illegal skip rejected | Handler writes target directly | Real endpoint from `prepare`, request `verify` | Reject; persisted state still `prepare`; no completion effect |
| Terminal immutable | Handler accepts any target | Real endpoint from terminal state | Reject; no write |
| Failure atomicity | Partial write before validation | Inject storage failure if supported | No committed partial state, expected error |

A unit test for the pure function remains useful, but cannot prove the endpoint uses it. An integration test should invoke the real production handler; mock only external I/O that is not under test. Demonstrate the illegal-skip test fails on the known bypass and passes after the authorized fix. Use a disposable fixture and verify failure reason. A test checking only that a helper was called is weaker than asserting the externally visible rejection and unchanged state.

## Test selection

- Numeric constraint 1–10: choose 0/1/10/11, an interior value and invalid type if exposed; assert rejection does not change state.
- Idempotent operation: repeat the same key and inject an acknowledgement loss. Assert one durable effect, not just two successful responses. Use a deterministic fake clock for retry schedule.
- Refactor: characterize the approved old outputs, errors and side effects, then compare new behavior; deliberately avoid encoding an identified bug as a requirement.
- External integration: validate schema/defaults and a real representative environment where acceptance requires it. A successful mock is limited evidence, not deployment proof.

Record commands and environment, actual result, observed vs inferred claims, and skipped checks. For registered Tasks, bind final artifacts before executing checks and invalidate after changes. Never create a passing result from this example alone.

Further reading: [Google, Test Behavior, Not Implementation](https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html) and [What Makes a Good End-to-End Test?](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html). The framework adapts these practices; no specific test pyramid ratio is mandated.
