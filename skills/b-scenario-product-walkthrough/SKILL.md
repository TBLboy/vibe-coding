---
name: b-scenario-product-walkthrough
description: "场景讲解/用场景走一遍 | Explain a complex product, platform, framework, workflow, or Skill pack through a realistic end-to-end work scenario instead of a feature list. Use when the user asks how a product works, how to use it, what a workflow does, or requests a concrete simulated walkthrough."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Scenario-Driven Product Walkthrough

## Mental model

Explain a product through a realistic end-to-end use situation so the user can predict what happens when they act. This is an operational mental model, not a feature inventory, source tutorial, product redesign or a claim of having executed a simulation. Use the user's actual domain and requested role, starting state and goal when known; label illustrative examples.

## Construct the scenario from evidence

- Read relevant documentation, code/config, screenshots or confirmed facts first. Establish the user's role/permissions, desired result, entry point, starting data/state and available capabilities. Ask only for an unavailable fact that changes the scenario. Separate documented behavior, evidence-derived behavior, illustrative inputs and unknowns; never invent automation, APIs, integrations or guarantees.
- Select one representative normal path that exercises the important capabilities; add a meaningful exception or decision and later change/resumption if supported. Use two short scenarios only when distinct roles or modes cannot be explained honestly in one. A hypothetical future capability must remain labeled as such.
- Walk through the sequence in user-visible order. For each material stage connect **user intent/action → system response → visible result/artifact/state → control boundary**. Explain who decides, what is automatic vs manual, what approval is needed and what a failure leaves behind. Use short concrete commands, state examples, screenshots or diagrams only when supported and useful; explain terms at first use.
- Cover initial setup, main work loop, collaboration between capabilities, state ownership/persistence, relevant error or ambiguity, later change/bug, interruption/recovery and ordinary daily use when applicable. Do not force irrelevant branches or make a lifecycle look like a mandatory one-way waterfall. Check that recovery, state transitions and user controls agree with the actual product.

## Output

State scenario and goal, starting context and chronological walkthrough; show a meaningful branch/iteration and practical daily-use summary when useful. A compact feature-to-scenario map helps when many capabilities cooperate, but is not mandatory for a short explanation. Depth follows the user's goal; do not bury the operational picture in internal implementation. Mark simulated/illustrative state and unverified behavior clearly. Do not treat the example as an approved requirement, run a real workflow, create state or modify code simply to explain it.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
