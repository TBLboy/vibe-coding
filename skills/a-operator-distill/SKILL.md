---
name: a-operator-distill
description: Distill repeated, evidence-backed project lessons and user working preferences into staged personal operating rules, reusable Skills, templates, or tool improvements without fossilizing one-off behavior.
license: MIT
compatibility: codex
metadata:
  stage: distillation
  output: knowledge-candidates
---

# Operator Distill

## Purpose

Gradually model how the user works well so future Agents can operate autonomously inside the same framework.

Distillation is a promotion pipeline, not automatic memory dumping.

## Candidate Types

- stable operator preference;
- decision heuristic;
- reusable engineering pattern;
- debugging pattern;
- domain knowledge;
- checklist/template;
- Skill improvement;
- Agent or plugin improvement;
- anti-pattern and warning.

## Promotion Stages

```text
observation
→ candidate
→ repeated-evidence
→ approved-rule
→ encoded-asset
→ evaluated
```

A one-off success normally remains a candidate.

## Candidate Record

Capture:

- statement;
- context and applicability;
- supporting projects/decisions/results;
- counterexamples;
- confidence;
- risk if generalized incorrectly;
- proposed target: constitution, Agent, Skill, template, plugin, or knowledge note;
- approval requirement;
- evaluation plan.

## Promotion Rules

Promote only when:

- the lesson repeats or has unusually strong causal evidence;
- applicability and exclusions are explicit;
- no important counterexample is ignored;
- the new rule does not conflict with higher-priority principles;
- risky personal preferences receive user approval;
- the encoded change has a test or evaluation scenario.

Do not store transient mood, accidental wording, or sensitive personal facts as operator rules.

## Outputs

Update `.project-log/distillation/candidates.yaml` and create proposed patches under `.project-log/distillation/proposals/` when appropriate.

Never silently overwrite global Skills or constitution files. Use diff → review → backup → apply → validate → rollback.
