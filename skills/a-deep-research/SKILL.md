---
name: a-deep-research
description: "深度调研/查资料/选型研究 | Conduct decision-oriented technical, product, market, or strategy research with scoped questions, traceable evidence, contrary evidence, trade-offs, and an actionable recommendation."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Deep Research

## Mental model and depth

Research reduces uncertainty that could change a decision. Define the decision, options (including current/no-change where credible), constraints, audience, scope and useful stopping point. Ask only for unavailable decision-critical facts. For a focused lookup use `b-web-research-tooling`; this Skill owns synthesis, trade-offs and recommendations across technical, product, market, strategy or due-diligence questions.

Choose a quick scan for orientation or a bounded implementation question; standard research for comparisons and selection; deep decision research for high-cost, high-impact or hard-to-reverse choices. Depth follows uncertainty and stakes, not source count or report length.

## Research method

- Map decision-critical questions and plausible hypotheses before reading deeply. Prioritize unknowns by how much their answer can change the decision. Check existing project constraints, versions and actual usage before comparing alternatives.
- Choose evidence that can resolve each question: primary documents, standards, upstream source/releases, direct measurements, maintained references or filings as appropriate. Use `b-web-research-tooling` for online retrieval; use local source/tests or safe isolated probes for project feasibility when authorized. Record publisher, date/version, claim and applicable conditions. Do not confuse vendor promises with measured results or source repetition with independent evidence.
- Compare viable options on common, decision-derived dimensions; separate hard disqualifiers from preferences. Normalize units, baseline, workload, platform, cost assumptions and time horizon where relevant. Mark incomparable results instead of inventing a ranking; avoid false precision and arbitrary weighted scores.
- Seek counterexamples, contradictory evidence, failure modes, switching/maintenance costs and conditions that would reverse the recommendation. Separate observed facts, analysis and assumptions; explain unresolved disagreement rather than averaging incompatible claims.
- Stop when more research is unlikely to alter the recommendation, or when a targeted experiment or user decision is needed. Acknowledge inaccessible evidence, uncertainty and limits. No forced full literature survey for a narrow question.

## Decision-ready result

Lead with recommendation and reasons, supporting sources and applicability, alternatives and trade-offs, key uncertainties, fallback/reversal conditions, and the smallest next validation action. A quick scan can be a few paragraphs; a durable decision report may be saved to `.vibe/docs/` when useful. Cite material external claims near the conclusion they support; avoid unsupported certainty.

A recommendation is not approval to implement or deploy. When an authorized choice affects registered work, use Runtime `record_decision` in prepare/implement; follow `docs/03-STATE-MACHINE.md` and the registered-criteria supersession rule in `docs/06-AGENT-CONTRACT.md` where applicable. Record durable project decisions in `.vibe/progress.md` as warranted; do not directly edit Task fields or create a Task merely to hold research notes.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
