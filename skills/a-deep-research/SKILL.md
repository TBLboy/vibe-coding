---
name: a-deep-research
description: "Conduct decision-oriented technical, product, market, or strategy research with scoped questions, traceable evidence, contrary evidence, trade-offs, and an actionable recommendation."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Deep Research

## Purpose

Research to support a decision, not to collect links. Use this for broad technical, product, commercial, competitive, roadmap, or due-diligence questions, and for precise implementation-path or library/technology selection (run it as a quick scan or standard research with the candidate options fixed up front).

## Scope

Classify the requested depth:

- **quick scan**: terminology and early signal; proceed with stated assumptions;
- **standard research**: comparison, selection, planning, or competitor assessment;
- **deep decision research**: high-cost, strategic, externally published, or difficult-to-reverse decisions.

For standard or deep work, establish the decision, audience, deadline, included and excluded scope, constraints, and deliverable before research. Ask only for an unavailable, decision-critical fact.

## Evidence Method

1. Build a research map before deep reading individual sources.
2. Prefer primary sources, official documentation, maintained upstream material, public filings, and direct evidence.
3. Use `b-web-research-tooling` when web search or retrieval is needed; use current official documentation for library or service details.
4. Compare serious options on the same dimensions.
5. Seek contrary evidence, failure cases, and conditions that invalidate the leading recommendation.
6. Separate facts, analysis, assumptions, open questions, and recommendations.

## Output

Write a decision-ready report with conclusion first, evidence citations, alternatives, trade-offs, risks, confidence, and the smallest next validation action when evidence is insufficient. When it changes the active project, record the chosen decision and its binding constraints in the active Task JSON `decisions` and, if durable, in `.vibe/progress.md`.

## Completion Gate

- every material claim has a traceable source;
- options are compared fairly;
- contrary evidence and uncertainty are visible;
- the recommendation has conditions and a fallback.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
