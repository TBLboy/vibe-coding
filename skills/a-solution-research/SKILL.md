---
name: a-solution-research
description: Research and compare mature technical solutions for a precise engineering problem, then recommend direct use, adaptation, reference implementation, or custom development with traceable evidence.
license: MIT
compatibility: codex
metadata:
  stage: solution-research
  output: technical-recommendation
---

# Solution Research

## Purpose

Make an engineering decision before writing unnecessary custom code. Prefer mature solutions for complex general-purpose capabilities, while retaining direct control over simple project-specific business logic.

## When to hand off to `a-deep-research`

This skill owns **precise implementation-path selection**. Do **not** expand every solution task into a full market/strategy brief.

Before candidate comparison, classify the problem:

| Situation | Action |
|-----------|--------|
| Capability, I/O, runtime, integration boundary, and constraints are clear enough to compare 2–N concrete technical options | Stay in `a-solution-research` |
| Scope is still product/market/strategy, multi-domain, high-cost, or hard to reverse, and those facts would change which technical options are valid | Load `a-deep-research` first; use its conclusion and constraints as inputs here |
| Only one narrow fact is missing (e.g. a library API detail) | Fetch that fact directly; do not open a full deep-research track |
| Evidence for implementation paths is insufficient after fair comparison | Prefer **spike-first** under Decision Strategies; deep research is not a substitute for the smallest experiment |

When handing off:

1. State the decision question, included/excluded scope, and what would make a recommendation invalid.
2. Run `a-deep-research` to the needed depth (`quick scan` / `standard research` / `deep decision research`).
3. Return here with: narrowed problem, hard constraints, options still in play, contrary evidence, and open questions that must not be silently assumed.
4. Record the handoff and resulting constraints in `.project-log/research/solution-research.yaml` and, when material, `decision-log.yaml`.

Do not treat `a-deep-research` output as an automatic architecture or vendor lock-in decision. Implementation strategy (`direct-use` / `wrapper-adapter` / `reference-implementation` / `custom` / `spike-first`) is still decided in this skill.

## Preconditions

Do not start with a vague topic. Establish:

- target capability;
- inputs and outputs;
- runtime and deployment environment;
- integration boundary;
- performance, latency, reliability, privacy, license, maintenance, and budget constraints;
- relevant business logic and acceptance criteria.

When a missing item is discoverable from the codebase, inspect it instead of asking the user.

If the topic is still too broad after one pass at preconditions, stop candidate search and follow **When to hand off to `a-deep-research`** instead of inventing a narrow problem.

## Evidence Priority

1. Official documentation and vendor SDKs.
2. Maintained upstream repositories and release notes.
3. Primary papers with maintained implementations.
4. Package registries and official examples.
5. Issue trackers and community experience as secondary evidence.
6. Tutorials and blogs only as supplementary leads.

For current technical facts, use current primary sources and record retrieval dates.

## Candidate Record

For each candidate capture:

- name and source;
- exact capability match;
- maintenance status and maturity;
- supported platforms/languages/hardware;
- integration model and API surface;
- dependencies and version constraints;
- performance evidence;
- license and commercial constraints;
- operational burden;
- migration/exit cost;
- known failure modes;
- project fit.

## Decision Strategies

Choose one:

- **direct-use**: mature, compatible, and solves the exact problem;
- **wrapper-adapter**: mature core with a project-owned boundary;
- **reference-implementation**: learn from existing work but own the implementation;
- **custom**: no suitable solution, strict constraints, or simple core business logic requiring control;
- **spike-first**: evidence is insufficient, so run the smallest experiment before committing.

Do not choose a framework merely because it is popular. Do not custom-build a weak substitute for a mature implementation without a recorded reason.

## Comparison

Use the same decision dimensions for all serious candidates. At minimum compare:

- requirement fit;
- integration cost;
- maintenance cost;
- performance;
- reliability;
- debuggability;
- lock-in and exit strategy;
- security/privacy;
- license/cost;
- risk.

State confidence and contrary evidence.

## Outputs

Update:

- `.project-log/research/solution-research.yaml`;
- `.project-log/decisions/decision-log.yaml`;
- affected tasks and workflow phase;
- architecture constraints when appropriate.

A recommendation must include conditions under which it would no longer be valid.

## Completion Gate

- the problem and constraints are precise;
- serious candidates were compared fairly;
- the recommendation has traceable evidence;
- implementation strategy and fallback are explicit;
- high-impact trade-offs use C-level confirmation where required.
