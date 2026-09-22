---
name: b-scenario-product-walkthrough
description: Explain a complex product, platform, framework, workflow, or Skill Pack through a realistic end-to-end work scenario instead of a feature list. Use when the user asks how a product works, how to use it, what a workflow does, or requests a concrete simulated walkthrough.
license: MIT
compatibility: codex
metadata:
  type: communication-skill-pack
  output: scenario-driven-product-walkthrough
---

# Scenario-Driven Product Walkthrough

## Purpose

Help users understand a product by placing its capabilities in a representative, realistic work situation. Explain what the user does, what the system does, what artifacts change, and how normal work, exceptions, and later changes are handled.

Use this instead of a feature inventory when the user needs an operational mental model.

## Inputs

Collect only what is needed:

- the product or workflow being explained;
- the intended user, role, and desired outcome;
- available documentation, code, configuration, screenshots, or prior facts;
- the user's requested depth and whether they want a new-project, existing-project, or troubleshooting scenario.

Read available evidence before asking. If key product behavior is undocumented, label the gap as an assumption or ask one focused question. Never invent APIs, automation, integrations, or guarantees.

## Scenario Selection

Choose one scenario that is concrete, representative, and broad enough to exercise the product's important capabilities. State the scenario in one sentence before starting.

Prefer a scenario that includes:

- the user's initial trigger and concrete goal;
- the normal success path;
- a meaningful decision, failure, or exception branch;
- a later change, bug fix, or resumed session when the product supports iteration;
- the resulting output and the user's normal daily operating pattern.

Use two short scenarios only when one cannot cover distinct user roles or product modes. Do not fabricate a fictional business domain merely for style; use the user's domain when known and otherwise identify the example as illustrative.

## Walkthrough Method

Present the work in chronological stages. For each stage, include:

1. **User intent or action**: what the user says, clicks, configures, or requests.
2. **System response**: which feature, workflow step, Agent, Skill, service, or integration acts and why.
3. **Visible result**: the artifact, state change, output, or decision the user can inspect.
4. **Control boundary**: what happens automatically, what remains manual, and when the system must ask the user.

Use short commands, snippets, state examples, or artifact trees only where they clarify the action. Explain terms at first use.

## Required Coverage

Cover the following when applicable:

- first-time setup or entry point;
- the main work loop from goal to usable result;
- how individual capabilities cooperate rather than listing them in isolation;
- important data, documents, task state, or durable artifacts;
- a realistic exception, ambiguity, failed validation, or decision branch;
- how a new request or bug revisits earlier work without restarting everything;
- interruption and recovery when state is persistent;
- the user's two or three practical daily usage patterns.

For workflows, explicitly distinguish a lifecycle from a one-way waterfall. For autonomous systems, state who chooses the next step and when user approval is required.

## Accuracy Rules

- Separate confirmed behavior, evidence-derived behavior, and illustrative assumptions.
- Do not claim a feature is automatic unless the product actually automates it.
- Do not turn an illustrative scenario into a requirement for the user's project.
- Match the terminology and interaction style used by the product.
- Keep internal implementation detail proportional to the user's goal.

## Output Shape

Use this outline unless the user requests another format:

```text
Scenario and goal
Starting context
Stage-by-stage walkthrough
Key branch or exception
Later change / bug / iteration
Daily-use summary
Feature-to-scenario map
```

End with a compact map from the major features to the moment in the scenario where each mattered. Offer a deeper technical walkthrough, role-specific variant, or a scenario based on the user's own project only if useful.
