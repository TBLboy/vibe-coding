---
name: b-source-code-tutoring
description: Teach an unfamiliar codebase through concrete source-level runtime traces rather than high-level module summaries. Use when the user asks to understand code deeply, read source together, explain a function line by line, trace a request/task/event through code, understand state variables, or build an internal model of an architecture before changing it.
license: MIT
metadata:
  type: interactive-code-learning
  routing: explicit-only
  output: source-grounded-learning-notes
---

# Source Code Tutoring

Teach the implementation, not only the architecture label. Build the explanation from actual classes, methods, variables, messages, callbacks, and call sites in the repository.

This Skill is explicit-only. Use it when the user asks to learn or trace code. Do not automatically turn a short code question into a full tutorial.

## Core Contract

For every explanation, establish this chain:

```text
concrete input
→ entry function/callback
→ object and state mutation
→ branch/guard evaluation
→ constructed output/message
→ downstream consumer
→ result callback or terminal state
```

Do not start with abstract labels such as “orchestrator”, “master-worker”, or “state machine”. Use those only after the source-level explanation, as a compact name for the observed code structure.

## Reading Workflow

1. Select one narrow, real execution path. Prefer the smallest runnable or testable path over the user’s final complex feature.
2. Locate the entry point, the next direct call, the data type crossing each boundary, and the terminal side effect.
3. Read only the necessary source around those symbols. Do not begin by listing every directory or module.
4. For each important function, explain:
   - caller and triggering condition;
   - input fields and pre-existing object state;
   - important lines in execution order;
   - fields mutated and why later code reads them;
   - return value/message and its next consumer.
5. Use one concrete value trace throughout when possible, such as `task_type="test_gripper"`, `request_id="r-1"`, or `user_id=42`.
6. Stop at the next boundary and let the user choose whether to continue. A boundary can be an RPC/Action call, queue publish, database write, subprocess, driver call, or framework callback.

## Required Explanation Shape

When explaining a non-trivial flow, present sections in this order.

### A. Source Anchors

Name the real files, classes, methods, and relevant line locations. State which source facts are confirmed and which downstream behavior is not yet read.

### B. Concrete Runtime Trace

Use an ordered time/event trace with a single example input. Do not invent timestamps, event names, object fields, or behavior; mark illustrative timing explicitly when the repository does not define it.

### C. State Lifecycle Table

For asynchronous, stateful, or multi-step code, include a table with the variable/object, initial value, writers, readers, effect on the next step, and terminal/reset value. Distinguish context, lifecycle state, busy/pending flags, policy step state, cached data, and correlation/epoch identifiers.

### D. Code-Level Interpretation

Explain key lines in source order. Connect each concrete object and field assignment to its next consumer. For line-by-line requests, do not skip lines or replace the implementation with pseudo-code.

### E. Engineering Model

Only after the source explanation, name a pattern if useful. The pattern is a compact description of observed source facts, not a replacement for the call trace.

## Function-Level Questions

When the user supplies a function, answer:

1. Who calls it and what framework/event invokes it?
2. What object state must already exist?
3. Which branch conditions can return early?
4. Which attributes, collections, or external systems does it mutate?
5. What does it return or send, and who consumes it next?
6. Which variables affect whether the function runs again?

## Accuracy Rules

- Read the actual implementation before asserting field assignments or routing behavior.
- Label pseudo-code as pseudo-code and correct prior illustrative statements when source differs.
- State when a framework-generated type comes from an IDL, schema, or action definition and show the defining file.
- Do not infer runtime success from static source; distinguish an existing code path from verified behavior.
- Do not silently broaden one execution path into a claim about the whole architecture.

## Learning Loop

After each path, provide:

```text
Input → state setup → guard → decision → message/output → downstream execution → result/state release
```

When the user wants a persistent note, record source anchors, the concrete trace, state lifecycle, confirmed interpretation, source gaps, and the next reading target.

## Exclusions

Do not use this Skill for a quick one-line definition, code review, broad onboarding without a selected execution path, or implementation planning before reading the relevant path.
