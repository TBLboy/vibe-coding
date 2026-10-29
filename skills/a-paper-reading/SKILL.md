---
name: a-paper-reading
description: "Read academic papers at selectable depth from relevance screening through structured understanding, methodological reconstruction, critical evaluation, and project transfer, producing traceable notes rather than generic summaries."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Paper Reading

## Purpose

Help the user understand a paper at the depth required for the current decision, presentation, reproduction, or research task.

## Reading Levels

### L0 — Relevance Screen

Goal: decide whether the paper deserves more time.

Extract:

- research question;
- claimed contribution;
- method family;
- dataset/experiment context;
- headline result;
- relevance to the user's problem;
- reasons to continue or stop.

### L1 — Rapid Understanding

Goal: explain the paper accurately in plain language.

Cover:

- problem and motivation;
- core idea;
- workflow;
- major experiments;
- main conclusion;
- limitations stated by authors;
- key terms the user must know.

### L2 — Structured Deep Read

Goal: reconstruct the argument section by section.

Cover:

- assumptions and definitions;
- method components and data flow;
- equations/algorithms with variable meanings;
- experiment design, baselines, metrics, and ablations;
- how each result supports or fails to support each claim;
- hidden dependencies and ambiguities.

### L3 — Reproduction Read

Goal: create a reproduction plan.

Extract:

- full pipeline;
- data and preprocessing;
- model/algorithm details;
- hyperparameters;
- training/inference procedure;
- hardware/software environment;
- evaluation protocol;
- missing details requiring inference;
- implementation references;
- smallest reproduction experiment and risks.

### L4 — Critical and Transfer Read

Goal: judge validity and transfer lessons into the user's work.

Analyze:

- novelty relative to prior work;
- causal strength and alternative explanations;
- statistical/methodological weaknesses;
- robustness and generalizability;
- contradictory evidence;
- what can be reused, adapted, or rejected;
- concrete implications for the user's project;
- new experiments or research questions.

## Reading Rules

- Distinguish author claims from demonstrated evidence and your interpretation.
- Cite page/section/figure/table/equation locations when the document supports it.
- Inspect figures and tables, not only extracted text.
- Explain equations by role, variables, assumptions, and derivation path as needed.
- Do not invent missing experimental details.
- For multiple papers, normalize comparison dimensions.
- Choose the lowest level that satisfies the user's goal; deepen selectively.

## Output Location

Notes are ordinary project documents; the layout below is a readability convention, not a framework-managed store. Place them where the user or the project `AGENTS.md` says (for example `docs/research/papers/<paper-slug>/`):

```text
<papers-root>/<paper-slug>/
  reading-note.md
  reproduction-plan.md   # L3+
  transfer-notes.md      # L4
```

The note begins with bibliographic identity, reading level, purpose, and one-paragraph conclusion. When a paper changes a project decision, record that decision in the active Task JSON `decisions` or `.vibe/progress.md`; do not copy the note there.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
