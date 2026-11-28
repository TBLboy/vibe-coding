---
name: a-paper-reading
description: "读论文/论文精读 | Read academic papers at selectable depth from relevance screening through structured understanding, methodological reconstruction, critical evaluation, and project transfer, producing traceable notes rather than generic summaries."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Paper Reading

## Mental model

Reconstruct the paper's claim → assumptions → method → evidence → limitations chain at the depth the user needs. A paper is evidence for a claim under specific conditions, not an implementation specification or proof of general applicability. Read the supplied version and identify title, authors, publication/version and source; distinguish unavailable sections from what was actually inspected.

## Reading levels

Choose the lowest useful level and deepen selectively; the levels are not a compulsory sequence.

| Level | Goal and key material |
|---|---|
| L0 — Relevance screen | Question, claimed contribution, method family, dataset/experiment context, headline result and why it is or is not relevant. |
| L1 — Rapid understanding | Motivation, central idea, workflow, major experiments, conclusion, author-stated limits and essential terminology. |
| L2 — Structured deep read | Definitions and assumptions, components/data flow, equations/algorithms, experimental design, baselines, metrics, ablations and claim-to-result links. |
| L3 — Reproduction read | Pipeline, data/splits/preprocessing, algorithm/model, hyperparameters, train/inference, software/hardware, evaluation protocol, code/artifact availability, missing details and smallest reproduction experiment. |
| L4 — Critical and transfer read | Novelty, alternative explanations, causal/statistical strength, robustness, generalization, contrary evidence, what can transfer to the user's project and what needs new tests. |

## Evidence and method

- Distinguish author claims, demonstrated results and your interpretation. Anchor important statements to page/section/figure/table/equation; inspect figures and tables, including axes, legends, units and captions, where available. If access or extraction is incomplete, state that limit instead of filling gaps.
- Explain an equation by its role, symbols, shapes/units where meaningful, assumptions and how it connects to computation. For algorithm questions trace inputs, transformations, outputs and training versus inference. Do not invent a derivation or missing hyperparameters.
- Test whether the evidence actually answers the claim: comparable baseline and protocol, dataset split/leakage risk, sample size/variation, uncertainty, ablations and alternative explanations as relevant. Distinguish correlation, controlled intervention and author speculation; do not infer superiority across incomparable benchmarks.
- For L3, separate documented settings, code/config evidence and reproduction assumptions. A plan is not a reproduced result. For L4, compare the paper's assumptions/resources/data distribution with the user's project; identify the transfer gap and a small falsifiable experiment before recommending adoption. For multiple papers, compare like-for-like settings and dates. Seek related work only when needed for the requested critique; label it as external evidence.

## Output and persistence

Give the conclusion, requested depth of explanation, source anchors, assumptions/limitations and relevant next question. Notes are ordinary project documents, not a new memory store. When a durable note is wanted, default to `.vibe/docs/papers/<paper-slug>/reading-note.md`; add `reproduction-plan.md` (L3+) or `transfer-notes.md` (L4) only when useful. Honor an authorized alternative location. Include bibliographic identity and reading level.

An adopted project decision needs the existing authority rules. For registered Tasks use `record_decision` in prepare/implement or the appropriate existing lifecycle event; keep durable decisions in `.vibe/progress.md` where warranted, not copies of paper notes. Do not claim experimental execution or modify the project solely because a paper recommends a technique.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
