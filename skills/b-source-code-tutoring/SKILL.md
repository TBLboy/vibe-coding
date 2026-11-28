---
name: b-source-code-tutoring
description: "源码讲解/逐行讲代码/代码跟读 | Teach an unfamiliar codebase through concrete source-level runtime traces rather than high-level module summaries. Use when the user asks to understand code deeply, read source together, explain a function line by line, trace a request/task/event through code, understand state variables, or build an internal model of an architecture before changing it."
license: MIT
compatibility: opencode
metadata:
  v2: true
  routing: explicit-only
---

# Source Code Tutoring

## Purpose

Teach the actual implementation using concrete source anchors, execution order, data and state rather than architecture labels. This Skill is explicit-only for learning, tracing or line-by-line explanation, not a quick definition, code review, broad onboarding or unsolicited implementation. Adapt to the user's familiarity and question; no edits or live side effects by default.

## Source-grounded method

Choose a narrow real path or the function the user names. Trace concrete input → entry function/callback → guards and state mutation in actual source order → constructed output/message → downstream consumer → result callback or terminal/reset state. Do not impose a state mutation or callback where none exists.

Locate the callers, registration/framework trigger, crossing types and next consumer; read necessary surrounding source and the definitions of generated types (IDL/schema/action) where relevant. Explain pre-existing state, branch conditions/early returns, key lines in order, mutations and why later code reads them, return values/effects and what makes the function execute again. Use one concrete example value consistently, marked illustrative if not observed. Resolve dynamic dispatch, scheduling and configuration only where evidence supports it. For async flows distinguish causal order from assumed timing; include error/cancellation/reset paths if they explain the state lifecycle.

Start with observed code, not abstract pattern names. Name a pattern afterward if it compresses the established understanding. Label pseudocode and any illustrative timestamps; never invent fields, events, consumers or runtime success. Correct previous illustrations when source differs. Distinguish static path, actual observed trace and unverified downstream behavior; one path does not prove the entire architecture.

## Explanation shape

For non-trivial paths use these views in order (see `references/teaching-template.md` for a detailed optional template):

- **Source anchors:** actual files, symbols, relevant lines and unread boundaries.
- **Concrete runtime trace:** one input through ordered events; distinguish illustrative sequence from measured timing.
- **State lifecycle:** for asynchronous/stateful/multi-step paths, variable/object, initial value, writers, readers, effect, terminal/reset. Separate context, lifecycle, busy/pending, policy step state, cache and correlation/epoch IDs when relevant.
- **Code-level interpretation:** actual lines in order, connecting fields to consumers. For line-by-line requests cover every requested line; never substitute pseudocode for the implementation.
- **Engineering model:** concise explanation/pattern only after grounding it in the source.

For a focused question use just the relevant views. At the natural next boundary (RPC, queue, database, subprocess, callback, driver), identify what consumes the object and what remains unread. Stop when the requested learning scope is satisfied; continue across boundaries without unnecessary questions if the user requested an end-to-end trace. Give a compact input → decisions/state → output → consumer summary when useful.

When the user wants a persistent note, use `.vibe/docs/code-notes/<topic>.md` or their requested path. Include source anchors, concrete trace, state lifecycle where relevant, confirmed interpretation, gaps and next reading target. Record only durable architectural facts in `.vibe/progress.md` when justified; do not create Tasks or execute code merely to teach a path.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
