---
name: a-paper-reading
description: Read academic papers at selectable depth from relevance screening through structured understanding, methodological reconstruction, critical evaluation, and project transfer, producing traceable notes rather than generic summaries.
license: MIT
compatibility: codex
metadata:
  domain: research
  levels: L0-L4
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

Default:

```text
.project-log/research/papers/<paper-slug>/
  reading-note.md
  reproduction-plan.md   # L3+
  transfer-notes.md      # L4
```

The note begins with bibliographic identity, reading level, purpose, and one-paragraph conclusion.
